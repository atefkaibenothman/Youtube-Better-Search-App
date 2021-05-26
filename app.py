import json
import sys
from flask import Flask, render_template, Markup, request
from run import output_data_to_file

app = Flask(__name__)

@app.route("/")
def home():
    data = {}
    return render_template("index.html", videos=data)

@app.route("/", methods=["POST"])
def home_post():
    search_term = request.form["search"]
    output_data_to_file(search_term)
    with open("./data.json") as f:
        data = json.load(f)
    return render_template("index.html", videos=data)

if __name__ == "__main__":
    app.run(debug=True)
