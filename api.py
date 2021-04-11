from selenium import webdriver
from configparser import ConfigParser
from time import time
from google.protobuf.json_format import MessageToDict
import gplay_pb2
import requests

def fparse(data):
    parsed = {}
    
    for line in data.splitlines():
        key, value = tuple(line.split("=", 1))
        parsed[key] = value
    
    return parsed

class GooglePlay:
    def __init__(self, user, auth_token=None, device="px_3a"):
        self.user = user
        self.gsf_id = None
        self.aas_token = None
        self.dcic_token = None
        self.dconf_token = None
        self.dfe_cookie = None
        self.auth_token = auth_token
        self.user_profile = None

        config = ConfigParser()
        config.read("device.properties")
        self.properties = config[device]
        
        self.checkin()
        self.upload_device_config()
        
        if self.auth_token is None:
            self.get_aas_token()
            self.get_auth_token()
        
        self.toc()
        self.get_user_profile()
    
    def from_config(filename):
        config = ConfigParser()
        config.read(filename)
        
        user = config["data"]["user"]
        auth_token = config["data"]["auth_token"]
        
        api = GooglePlay(user, auth_token=auth_token)
        return api
    
    def to_config(self, filename):
        config = ConfigParser()
        config["data"] = {
            "user": self.user,
            "auth_token": self.auth_token
        }
        
        with open(filename, "w") as f:
            config.write(f)
    
    @property
    def user_agent(self):
        params = [
            "api=3",
            f"versionCode=" + self.properties['vending.version'],
            f"sdk=" + self.properties['build.version.sdk_int'],
            f"device=" + self.properties['build.device'],
            f"hardware=" + self.properties['build.hardware'],
            f"product=" + self.properties['build.product'],
            f"platformVersionRelease=" + self.properties['build.version.release'],
            f"model=" + self.properties['build.model'],
            f"buildId=" + self.properties['build.id'],
            "isWideScreen=0",
            f"supportedAbis=" + self.properties['platforms'].replace(',', ';')
        ]
        
        return "Android-Finsky/" + self.properties.get('vending.versionstring', '8.4.19.V-all [0] [FP] 175058788') + f" ({','.join(params)})"
    
    @property
    def auth_headers(self):
        headers = {
            "app": "com.google.android.gms",
            "User-Agent": f"GoogleAuth/1.4 ({self.properties['build.device']}) " + self.properties['build.id']
        }
        
        if self.gsf_id:
            headers["device"] = self.gsf_id
        
        return headers
    
    @property
    def headers(self):
        headers = {
            "User-Agent": self.user_agent,
            "X-DFE-Device-Id": self.gsf_id,
            "Accept-Language": "en-US",
            "X-DFE-Encoded-Targets": "CAESN/qigQYC2AMBFfUbyA7SM5Ij/CvfBoIDgxHqGP8R3xzIBvoQtBKFDZ4HAY4FrwSVMasHBO0O2Q8akgYRAQECAQO7AQEpKZ0CnwECAwRrAQYBr9PPAoK7sQMBAQMCBAkIDAgBAwEDBAICBAUZEgMEBAMLAQEBBQEBAcYBARYED+cBfS8CHQEKkAEMMxcBIQoUDwYHIjd3DQ4MFk0JWGYZEREYAQOLAYEBFDMIEYMBAgICAgICOxkCD18LGQKEAcgDBIQBAgGLARkYCy8oBTJlBCUocxQn0QUBDkkGxgNZQq0BZSbeAmIDgAEBOgGtAaMCDAOQAZ4BBIEBKUtQUYYBQscDDxPSARA1oAEHAWmnAsMB2wFyywGLAxol+wImlwOOA80CtwN26A0WjwJVbQEJPAH+BRDeAfkHK/ABASEBCSAaHQemAzkaRiu2Ad8BdXeiAwEBGBUBBN4LEIABK4gB2AFLfwECAdoENq0CkQGMBsIBiQEtiwGgA1zyAUQ4uwS8AwhsvgPyAcEDF27vApsBHaICGhl3GSKxAR8MC6cBAgItmQYG9QIeywLvAeYBDArLAh8HASI4ELICDVmVBgsY/gHWARtcAsMBpALiAdsBA7QBpAJmIArpByn0AyAKBwHTARIHAX8D+AMBcRIBBbEDmwUBMacCHAciNp0BAQF0OgQLJDuSAh54kwFSP0eeAQQ4M5EBQgMEmwFXywFo0gFyWwMcapQBBugBPUW2AVgBKmy3AR6PAbMBGQxrUJECvQR+8gFoWDsYgQNwRSczBRXQAgtRswEW0ALMAREYAUEBIG6yATYCRE8OxgER8gMBvQEDRkwLc8MBTwHZAUOnAXiiBakDIbYBNNcCIUmuArIBSakBrgFHKs0EgwV/G3AD0wE6LgECtQJ4xQFwFbUCjQPkBS6vAQqEAUZF3QIM9wEhCoYCQhXsBCyZArQDugIziALWAdIBlQHwBdUErQE6qQaSA4EEIvYBHir9AQVLmgMCApsCKAwHuwgrENsBAjNYswEVmgIt7QJnN4wDEnta+wGfAcUBxgEtEFXQAQWdAUAeBcwBAQM7rAEJATJ0LENrdh73A6UBhAE+qwEeASxLZUMhDREuH0CGARbd7K0GlQo",
            "X-DFE-Phenotype": "H4sIAAAAAAAAAB3OO3KjMAAA0KRNuWXukBkBQkAJ2MhgAZb5u2GCwQZbCH_EJ77QHmgvtDtbv-Z9_H63zXXU0NVPB1odlyGy7751Q3CitlPDvFd8lxhz3tpNmz7P92CFw73zdHU2Ie0Ad2kmR8lxhiErTFLt3RPGfJQHSDy7Clw10bg8kqf2owLokN4SecJTLoSwBnzQSd652_MOf2d1vKBNVedzg4ciPoLz2mQ8efGAgYeLou-l-PXn_7Sna1MfhHuySxt-4esulEDp8Sbq54CPPKjpANW-lkU2IZ0F92LBI-ukCKSptqeq1eXU96LD9nZfhKHdtjSWwJqUm_2r6pMHOxk01saVanmNopjX3YxQafC4iC6T55aRbC8nTI98AF_kItIQAJb5EQxnKTO7TZDWnr01HVPxelb9A2OWX6poidMWl16K54kcu_jhXw-JSBQkVcD_fPsLSZu6joIBAAA",
            "X-DFE-Client-Id": "am-android-google",
            "X-DFE-Network-Type": "4",
            "X-DFE-Content-Filters": "",
            "X-Limit-Ad-Tracking-Enabled": "false",
            "X-Ad-Id": "GooglePlay",
            "X-DFE-UserLanguages": "en-US",
            "X-DFE-Request-Params": "timeoutMs=4000"
        }
        
        if self.auth_token:
            headers["Authorization"] = "Bearer " + self.auth_token
        
        if self.dcic_token:
            headers["X-DFE-Device-Checkin-Consistency-Token"] = self.dcic_token
        
        if self.dconf_token:
            headers["X-DFE-Device-Config-Token"] = self.dcic_token
        
        if self.dfe_cookie:
            headers["X-DFE-Cookie"] = self.dfe_cookie
        
        if self.properties.get("simoperator", "None") != "None":
            headers["X-DFE-MCCMNC"] = self.properties["simoperator"]
        
        return headers
    
    def api_request(self, url, params=None, data=None, post=False):
        if post and (data is None):
            resp_content = requests.post(url, headers=self.headers, params=params).content
        elif data:
            resp_content = requests.post(url, headers=self.headers, data=data.SerializeToString(), params=params).content
        else:
            resp_content = requests.get(url, headers=self.headers, params=params).content
        
        return gplay_pb2.ResponseWrapper.FromString(resp_content).payload
    
    def get_aas_token(self):
        profile = webdriver.FirefoxProfile()
        profile.set_preference("dom.webdriver.enabled", False)
        profile.set_preference('useAutomationExtension', False)
        profile.set_preference('devtools.jsonview.enabled', False)
        driver = webdriver.Firefox(firefox_profile=profile)
        
        driver.implicitly_wait(5)
        
        driver.get("https://accounts.google.com/EmbeddedSetup/identifier?flowName=EmbeddedSetupAndroid")
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        user_field = driver.find_element_by_xpath('//*[@id="identifierId"]')
        user_field.send_keys(self.user + "\n")
        
        while driver.get_cookie("oauth_token") is None:
            pass
        
        token = driver.get_cookie("oauth_token")["value"]
        driver.quit()
        
        data = {
            "lang": "en",
            "google_play_services_version": self.properties["gsf.version"],
            "sdk_version": self.properties['build.version.sdk_int'],
            "device_country": "us",
            "Email": self.user,
            "service": "ac2dm",
            "get_accountid": 1,
            "ACCESS_TOKEN": 1,
            "callerPkg": "com.google.android.gms",
            "add_account": 1,
            "Token": token,
            "callerSig": "38918a453d07199354f8b19af05ec6562ced5788"
        }
        
        headers = self.auth_headers
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        
        self.aas_token = fparse(requests.post("https://android.clients.google.com/auth", data=data, headers=headers).text)["Token"]
    
    def checkin(self):
        android_build = gplay_pb2.AndroidBuildProto()
        android_build.id = self.properties["build.fingerprint"]
        android_build.product = self.properties["build.hardware"]
        android_build.carrier = self.properties["build.brand"]
        android_build.radio = self.properties["build.radio"]
        android_build.bootloader = self.properties["build.bootloader"]
        android_build.device = self.properties["build.device"]
        android_build.sdkVersion = self.properties.getint("build.version.sdk_int")
        android_build.model = self.properties["build.model"]
        android_build.manufacturer = self.properties["build.manufacturer"]
        android_build.buildProduct = self.properties["build.product"]
        android_build.client = self.properties["client"]
        android_build.otaInstalled = False
        android_build.timestamp = int(time()/1000)
        android_build.googleServices = self.properties.getint("gsf.version")
        
        device_config = gplay_pb2.DeviceConfigurationProto()
        device_config.touchScreen = self.properties.getint("touchscreen")
        device_config.keyboard = self.properties.getint("keyboard")
        device_config.navigation = self.properties.getint("navigation")
        device_config.screenLayout = self.properties.getint("screenlayout")
        device_config.hasHardKeyboard = self.properties.getboolean("hashardkeyboard")
        device_config.hasFiveWayNavigation = self.properties.getboolean("hasfivewaynavigation")
        device_config.screenDensity = self.properties.getint("screen.density")
        device_config.screenWidth = self.properties.getint("screen.width")
        device_config.screenHeight = self.properties.getint("screen.height")
        device_config.glEsVersion = self.properties.getint("gl.version")
        device_config.nativePlatform[:] = self.properties["platforms"].split(",")
        device_config.systemSharedLibrary[:] = self.properties["sharedlibraries"].split(",")
        device_config.systemAvailableFeature[:] = self.properties["features"].split(",")
        device_config.systemSupportedLocale[:] = self.properties["locales"].split(",")
        device_config.glExtension[:] = self.properties["gl.extensions"].split(",")
        self.device_config = device_config
        
        checkin = gplay_pb2.AndroidCheckinProto()
        checkin.build.CopyFrom(android_build)
        checkin.lastCheckinMsec = 0
        checkin.cellOperator = self.properties["celloperator"]
        checkin.simOperator = self.properties["simoperator"]
        checkin.roaming = self.properties["roaming"]
        checkin.userNumber = 0
        
        request = gplay_pb2.AndroidCheckinRequest()
        request.id = 0
        request.checkin.CopyFrom(checkin)
        request.locale = "en_US"
        request.timeZone = self.properties.get("timezone", "Europe/Stockholm")
        request.version = 3
        request.deviceConfiguration.CopyFrom(device_config)
        request.fragment = 0
        
        headers = self.auth_headers
        headers["Content-Type"] = "application/x-protobuffer"
        headers["Host"] = "android.clients.google.com"
        
        resp_content = requests.post("https://android.clients.google.com/checkin",
                headers=headers,
                data=request.SerializeToString()
        ).content
        response = gplay_pb2.AndroidCheckinResponse.FromString(resp_content)
        
        self.gsf_id = hex(response.androidId)[2:]
        self.dcic_token = response.deviceCheckinConsistencyToken
    
    def upload_device_config(self):
        request = gplay_pb2.UploadDeviceConfigRequest()
        request.deviceConfiguration.CopyFrom(self.device_config)
        response = self.api_request("https://android.clients.google.com/fdfe/uploadDeviceConfig", data=request)
        
        self.dconf_token = response.uploadDeviceConfigResponse.uploadDeviceConfigToken
    
    def get_auth_token(self):
        data = {
            "androidId": self.gsf_id,
            "app": "com.android.vending",
            "lang": "en",
            "google_play_services_version": self.properties["gsf.version"],
            "sdk_version": self.properties['build.version.sdk_int'],
            "device_country": "us",
            "Email": self.user,
            "callerPkg": "com.google.android.gms",
            "service": "oauth2:https://www.googleapis.com/auth/googleplay",
            "Token": self.aas_token,
            "callerSig": "38918a453d07199354f8b19af05ec6562ced5788",
            "client_sig": "38918a453d07199354f8b19af05ec6562ced5788",
            "oauth2_foreground": 1,
            "token_request_options": "CAA4AVAB",
            "check_email": 1,
            "system_partition": 1
        }
        
        headers = self.headers
        headers["app"] = "com.google.android.gms"
        self.auth_token = fparse(requests.post("https://android.clients.google.com/auth", headers=headers, data=data).text)["Auth"]
    
    def toc(self):
        response = self.api_request("https://android.clients.google.com/fdfe/api/toc")
        toc_resp = response.tocResponse
        
        if toc_resp.tosContent and toc_resp.tosToken:
            data = {
                "tost": toc_resp.tosToken,
                "toscme": "false"
            }
            
            requests.post("https://android.clients.google.com/fdfe/api/acceptTos", headers=self.headers, data=data)
        
        if toc_resp.cookie:
            self.dfe_cookie = toc_resp.cookie
    
    def get_user_profile(self):
        resp_content = requests.get("https://android.clients.google.com/fdfe/api/userProfile", headers=self.headers).content
        wrapper = gplay_pb2.ResponseWrapperApi.FromString(resp_content)
        self.user_profile = MessageToDict(wrapper.payload.userProfileResponse)
    
    def details(self, package):
        return MessageToDict(self.api_request("https://android.clients.google.com/fdfe/details", params={"doc": package}).detailsResponse.docV2)
    
    def search(self, query):
        response = self.api_request("https://android.clients.google.com/fdfe/searchList", params={"q": query, "c": 3}).listResponse.doc
        results = []
        
        for item_list in response:
            for sub_list in item_list.child:
                if sub_list.docType == 45:
                    for item in sub_list.child:
                        if item.docType == 1:
                            results.append(MessageToDict(item))
        
        return results
    
    def delivery(self, package, version_code, offer_type=1, download_token=None):
        params = {
            "ot": offer_type,
            "doc": package,
            "vc": version_code
        }
        params["dtok"] = download_token
        
        return MessageToDict(self.api_request("https://android.clients.google.com/fdfe/delivery", params=params).deliveryResponse.appDeliveryData)
    
    def purchase(self, package, version_code, offer_type=1):
        return self.api_request("https://android.clients.google.com/fdfe/purchase", params={"ot": offer_type, "doc": package, "vc": version_code}, post=True).buyResponse.downloadToken
    
    def reviews(self, package, number=None):
        params = {
            "doc": package,
            "sort": "2"
        }
        
        if number:
            params["n"] = str(number)
        
        reviews = self.api_request("https://android.clients.google.com/fdfe/rev", params=params).reviewResponse.getResponse.review
        return list(map(MessageToDict, reviews))
