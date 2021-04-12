from flask import Flask, request, Response, jsonify
from api import GooglePlay

app = Flask(__name__)
api = GooglePlay.from_config("auth.conf")

app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

@app.route("/api/details")
def details():
    doc = request.args["id"]
    
    return jsonify(api.details(doc))

@app.route("/api/search")
def search():
    query = request.args["q"]
    
    return jsonify(api.search(query))

@app.route("/api/downloads")
def downloads():
    doc = request.args["id"]
    
    vc = api.details(doc)["details"]["appDetails"]["versionCode"]
    delivery = api.delivery(doc, vc)
    
    if delivery:
        return jsonify(delivery)
    else:
        api.purchase(doc, vc)
        return jsonify(api.delivery(doc, vc))

@app.route("/api/reviews")
def reviews():
    doc = request.args["id"]
    
    return jsonify(api.reviews(doc))

if __name__ == "__main__":
    app.run(host="0.0.0.0")
