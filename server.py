"""
Backend API for the electrolyte additive research screener.

Wraps pubmed_electrolyte_scraper.py's real PubMed E-utilities calls behind
a small HTTP API so the React UI (ElectrolyteScreenerApp.jsx) can search
and export actual PubMed results instead of hardcoded demo data.

Run with:
    pip install -r requirements.txt
    python server.py
"""

import io
import os

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import pandas as pd

from pubmed_electrolyte_scraper import fetch_paper_details, search_pubmed

app = Flask(__name__)
CORS(app)

DEFAULT_KEYWORD = '(lithium battery electrolyte additive) AND (SEI OR "high temperature" OR "cycling stability")'


def run_search(keyword, max_results):
    ids = search_pubmed(keyword, max_results)
    return fetch_paper_details(ids)


@app.get("/api/search")
def api_search():
    keyword = request.args.get("keyword", DEFAULT_KEYWORD)
    max_results = min(max(request.args.get("max", default=10, type=int), 1), 50)
    try:
        papers = run_search(keyword, max_results)
    except Exception as e:
        return jsonify({"error": f"PubMed 검색에 실패했습니다: {e}"}), 502
    return jsonify(papers)


@app.get("/api/export")
def api_export():
    keyword = request.args.get("keyword", DEFAULT_KEYWORD)
    max_results = min(max(request.args.get("max", default=10, type=int), 1), 50)
    try:
        papers = run_search(keyword, max_results)
    except Exception as e:
        return jsonify({"error": f"PubMed 검색에 실패했습니다: {e}"}), 502

    df = pd.DataFrame(papers, columns=["pmid", "title", "authors", "journal", "pubdate", "url", "abstract"])
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="electrolyte_research_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
