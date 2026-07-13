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

# 전해액 연구 도메인으로 검색 결과를 좁히기 위한 보조 용어들.
# 사용자가 짧은 키워드(예: "SEI", "high voltage")만 입력해도 배터리/전해액
# 맥락의 논문 위주로 나오도록 제목/초록(tiab) 필드에 한정해 AND 결합한다.
DOMAIN_TERMS = ["lithium", "electrolyte", "battery", "anode", "cathode", "SEI"]

# PubMed 구조화 초록(Structured Abstract)의 <AbstractText Label="..."> 값을
# "실험 조건"/"핵심 결과" 카테고리로 매핑. 값은 실제 논문이 제공하는 라벨 그대로이며,
# 라벨이 없는 논문은 구조화하지 않고 전체 초록만 반환한다(임의 생성/요약 없음).
ABSTRACT_LABEL_MAP = {
    "methods": {"METHODS", "MATERIALS AND METHODS", "MATERIALS", "EXPERIMENTAL",
                "EXPERIMENTAL SECTION", "STUDY DESIGN", "METHODOLOGY"},
    "results": {"RESULTS", "FINDINGS", "RESULTS AND DISCUSSION"},
    "background": {"BACKGROUND", "INTRODUCTION", "OBJECTIVE", "OBJECTIVES", "PURPOSE", "AIM", "AIMS"},
    "conclusion": {"CONCLUSION", "CONCLUSIONS", "DISCUSSION", "SIGNIFICANCE"},
}


def _abstract_category(label):
    label_u = (label or "").strip().upper()
    for category, aliases in ABSTRACT_LABEL_MAP.items():
        if label_u in aliases:
            return category
    return None


def build_relevance_query(keyword):
    """사용자 키워드를 전해액/배터리 연구 맥락에 한정하는 쿼리로 확장한다."""
    keyword = (keyword or "").strip() or SEARCH_KEYWORD
    domain_clause = " OR ".join(f"{term}[tiab]" for term in DOMAIN_TERMS)
    return f"({keyword}) AND ({domain_clause})"


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

        sections = {"methods": [], "results": [], "background": [], "conclusion": []}
        abstract_parts = []
        for a in art.findall(".//AbstractText"):
            text = "".join(a.itertext()).strip()
            if not text:
                continue
            abstract_parts.append(text)
            category = _abstract_category(a.get("Label"))
            if category:
                sections[category].append(text)

        abstract = " ".join(abstract_parts)
        methods = " ".join(sections["methods"])
        results = " ".join(sections["results"])
        background = " ".join(sections["background"])
        conclusion = " ".join(sections["conclusion"])
        structured = bool(methods or results)

        journal = art.findtext(".//Article/Journal/Title", default="")
        pubdate = art.findtext(".//Article/Journal/JournalIssue/PubDate/Year")
        if not pubdate:
            pubdate = art.findtext(".//Article/Journal/JournalIssue/PubDate/MedlineDate", default="")

        papers.append({
            "pmid": pmid,
            "title": title,
            "authors": ", ".join(authors),
            "abstract": abstract,
            "methods": methods,
            "results": results,
            "background": background,
            "conclusion": conclusion,
            "structured": structured,
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
