import requests
import xml.etree.ElementTree as ET
import pandas as pd
import time

# [정확도 개선] 전해액 첨가제 연구원님을 위한 맞춤형 정밀 검색 키워드 조합
# 리튬이온 배터리 전해액 첨가제이면서 SEI 피막이나 성능 향상과 직접 관련된 논문만 타겟팅합니다.
SEARCH_KEYWORD = '(lithium battery electrolyte additive) AND (SEI OR "high temperature" OR "cycling stability")'
MAX_RESULTS = 10
NCBI_EMAIL = "gml814@naver.com"
OUTPUT_FILENAME = "electrolyte_research_report_fixed.xlsx"

def search_pubmed(keyword, max_results=10):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": keyword,
        "retmax": max_results,
        "sort": "relevance",  # 가장 관련성 높은 논문 우선 정렬
        "retmode": "json",
        "email": NCBI_EMAIL
    }
    response = requests.get(url, params=params, timeout=30).json()
    return response.get("esearchresult", {}).get("idlist", [])

def fetch_paper_details(ids):
    if not ids:
        return []

    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {
        "db": "pubmed",
        "id": ",".join(ids),
        "rettype": "abstract",
        "retmode": "xml",
        "email": NCBI_EMAIL
    }
    headers = {
        "User-Agent": f"Python Script ({NCBI_EMAIL})"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        root = ET.fromstring(response.content)
    except Exception as e:
        print(f"논문 정보 수집 실패: {e}")
        return []

    papers = []
    for art in root.findall(".//PubmedArticle"):
        pmid = art.findtext(".//MedlineCitation/PMID", default="")

        te = art.find(".//ArticleTitle")
        title = "".join(te.itertext()) if te is not None else ""

        authors = []
        for au in art.findall(".//Author"):
            ln = au.find("LastName")
            ini = au.find("Initials")
            if ln is not None:
                authors.append(ln.text + (" " + ini.text if ini is not None else ""))

        abstract = " ".join("".join(a.itertext()) for a in art.findall(".//AbstractText"))

        journal = art.findtext(".//Article/Journal/Title", default="")
        pubdate = art.findtext(".//Article/Journal/JournalIssue/PubDate/Year")
        if not pubdate:
            pubdate = art.findtext(".//Article/Journal/JournalIssue/PubDate/MedlineDate", default="")

        papers.append({
            "pmid": pmid,
            "title": title,
            "authors": ", ".join(authors),
            "abstract": abstract,
            "journal": journal,
            "pubdate": pubdate or "",
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
        })
    return papers

def main():
    print(f"🔍 키워드 [{SEARCH_KEYWORD}] 로 배터리 전문 논문 수집을 시작합니다...")
    try:
        ids = search_pubmed(SEARCH_KEYWORD, MAX_RESULTS)
    except Exception as e:
        print(f"❌ PubMed 검색 중 에러 발생: {e}")
        return
    print("📌 분석 대상 논문 ID 개수:", len(ids))

    if not ids:
        print("❌ 관련 논문을 찾지 못했습니다.")
        return

    papers = fetch_paper_details(ids)
    print("📄 상세 초록 수집 완료 논문 개수:", len(papers))

    # Claude가 분석하기 좋게 데이터프레임으로 먼저 변환합니다.
    df = pd.DataFrame(papers)

    # 파일 저장 (Claude가 이 파일을 기반으로 데이터 분석 기능 창에서 직접 요약할 것입니다)
    df.to_excel(OUTPUT_FILENAME, index=False, engine="openpyxl")
    print(f"🎉 성공적으로 베이스 논문 파일 [{OUTPUT_FILENAME}]이 준비되었습니다.")

if __name__ == "__main__":
    main()
