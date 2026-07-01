"""
research/elite_sources.py — ELITE tədqiqat mənbələri (pulsuz, key istəmir).
Hər biri müstəqil işləyir, HTTP ilə. Heç bir ödənişli API tələb etmir.

Mövcud mənbələr:
  • arXiv        — akademik preprintlər (AI, fizika, riyaziyyat, CS)
  • OpenAlex     — 250M+ akademik iş, bütün sahələr
  • Semantic Scholar — AI/ML tədqiqat, sitat qrafı
  • PubMed       — biotibbi, səhiyyə
  • SEC EDGAR    — ABŞ korporativ maliyyə hesabatları
  • World Bank   — qlobal iqtisadi göstəricilər
  • GitHub       — kod, layihə, tendensiyalar
  • Hacker News  — texnoloji müzakirələr
  • Wikidata     — strukturlaşdırılmış bili (SPARQL)
  • VirusTotal   — malware/hash (pulsuz tier)
  • OpenCorporates — şirkət reyestri
  • OpenSanctions — sanksiyalar, PEP-lər
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any


UA = "AvtonomCogitate/1.0 (research; mailto:research@avtonomcogitate.local)"


def _http_get(url: str, headers: dict | None = None, timeout: int = 30, max_retries: int = 2) -> tuple[int, str]:
    """HTTP GET, heç bir xarici asılılıq yoxdur. 429 → retry."""
    import time as _time
    req_headers = {"User-Agent": UA, **(headers or {})}
    last_err = ""
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url, headers=req_headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                # 429 rate limit
                if r.status == 429 and attempt < max_retries:
                    wait = 2 ** attempt
                    _time.sleep(wait)
                    continue
                return r.status, r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries:
                wait = 2 ** attempt
                _time.sleep(wait)
                continue
            return 0, f"HTTPError {e.code}: {e.reason}"
        except Exception as e:
            last_err = str(e)
            if attempt < max_retries:
                _time.sleep(1)
                continue
            return 0, last_err
    return 0, last_err or "max retries"


# ════════════════════════════════════════════════════════════════
# 1) arXiv — akademik preprintlər
# ════════════════════════════════════════════════════════════════
def arxiv_search(query: str, max_results: int = 5) -> dict:
    """
    arXiv API: http://export.arxiv.org/api/query
    AI, fizika, riyaziyyat, CS, statistika, iqtisadiyyat preprintlər.
    """
    q = urllib.parse.quote(f"all:{query}")
    url = f"http://export.arxiv.org/api/query?search_query={q}&start=0&max_results={max_results}&sortBy=relevance&sortOrder=descending"
    status, body = _http_get(url)
    if status != 200:
        return {"source": "arxiv", "error": body, "results": []}
    # Atom XML parse
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    try:
        root = ET.fromstring(body)
        entries = root.findall("atom:entry", ns)
    except Exception as e:
        return {"source": "arxiv", "error": f"parse: {e}", "results": []}

    results = []
    for e in entries:
        title = (e.findtext("atom:title", default="", namespaces=ns) or "").strip().replace("\n", " ")
        summary = (e.findtext("atom:summary", default="", namespaces=ns) or "").strip().replace("\n", " ")[:500]
        link_el = e.find("atom:id", ns)
        link = link_el.text if link_el is not None else ""
        authors = [a.findtext("atom:name", default="", namespaces=ns) or "" for a in e.findall("atom:author", ns)]
        published = e.findtext("atom:published", default="", namespaces=ns) or ""
        # Kateqoriya
        cats = [c.attrib.get("term", "") for c in e.findall("arxiv:category", ns)]
        results.append({
            "title": title,
            "summary": summary,
            "url": link,
            "authors": authors[:5],
            "published": published[:10],
            "categories": cats,
        })
    return {"source": "arxiv", "query": query, "count": len(results), "results": results}


# ════════════════════════════════════════════════════════════════
# 2) OpenAlex — 250M+ akademik iş
# ════════════════════════════════════════════════════════════════
def openalex_search(query: str, max_results: int = 5) -> dict:
    """
    OpenAlex API: https://api.openalex.org/works?search=...
    Bütün sahələr üzrə akademik iş, sitatlar, müəlliflər.
    """
    q = urllib.parse.quote(query)
    url = f"https://api.openalex.org/works?search={q}&per_page={max_results}&sort=relevance_score:desc&select=id,doi,title,authorships,publication_year,cited_by_count,concepts,abstract_inverted_index"
    status, body = _http_get(url, headers={"Accept": "application/json"})
    if status != 200:
        return {"source": "openalex", "error": body, "results": []}
    try:
        data = json.loads(body)
    except Exception as e:
        return {"source": "openalex", "error": f"parse: {e}", "results": []}
    results = []
    for w in data.get("results", [])[:max_results]:
        # Abstract inverted index-dən bərpa et (çox kobud, amma işləyir)
        inv = w.get("abstract_inverted_index") or {}
        if inv:
            # Position-a görə sözləri düz
            words = [""] * (max((p for positions in inv.values() for p in positions), default=0) + 1)
            for word, positions in inv.items():
                for p in positions:
                    if p < len(words):
                        words[p] = word
            abstract = " ".join(words)[:500]
        else:
            abstract = ""
        results.append({
            "title": w.get("title") or "",
            "year": w.get("publication_year"),
            "cited_by": w.get("cited_by_count", 0),
            "doi": w.get("doi"),
            "url": w.get("id"),
            "authors": [a.get("author", {}).get("display_name", "") for a in w.get("authorships", [])][:5],
            "concepts": [c.get("display_name", "") for c in (w.get("concepts") or [])][:5],
            "abstract": abstract,
        })
    return {"source": "openalex", "query": query, "count": len(results), "results": results}


# ════════════════════════════════════════════════════════════════
# 3) Semantic Scholar — AI/ML tədqiqat
# ════════════════════════════════════════════════════════════════
def semantic_scholar_search(query: str, max_results: int = 5) -> dict:
    """
    Semantic Scholar API: https://api.semanticscholar.org/graph/v1/paper/search
    AI, ML, NLP üzrə dərin tədqiqat.
    """
    q = urllib.parse.quote(query)
    fields = "title,abstract,year,citationCount,authors,url,venue,publicationTypes,externalIds"
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={q}&limit={max_results}&fields={fields}"
    status, body = _http_get(url, headers={"Accept": "application/json"})
    if status != 200:
        return {"source": "semantic_scholar", "error": body, "results": []}
    try:
        data = json.loads(body)
    except Exception as e:
        return {"source": "semantic_scholar", "error": f"parse: {e}", "results": []}
    results = []
    for p in data.get("data", [])[:max_results]:
        results.append({
            "title": p.get("title", ""),
            "year": p.get("year"),
            "citations": p.get("citationCount", 0),
            "venue": p.get("venue", ""),
            "url": p.get("url"),
            "authors": [a.get("name", "") for a in (p.get("authors") or [])][:5],
            "abstract": (p.get("abstract") or "")[:500],
        })
    return {"source": "semantic_scholar", "query": query, "count": len(results), "results": results}


# ════════════════════════════════════════════════════════════════
# 4) PubMed — biotibbi, səhiyyə
# ════════════════════════════════════════════════════════════════
def pubmed_search(query: str, max_results: int = 5) -> dict:
    """
    PubMed E-utilities API: eutils.ncbi.nlm.nih.gov
    Biotibbi, səhiyyə, genetika, klinik tədqiqatlar.
    """
    q = urllib.parse.quote(query)
    # 1) search — ID-ləri al
    url_search = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={q}&retmax={max_results}&sort=relevance&retmode=json"
    status, body = _http_get(url_search)
    if status != 200:
        return {"source": "pubmed", "error": body, "results": []}
    try:
        ids = json.loads(body).get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        return {"source": "pubmed", "error": f"parse: {e}", "results": []}
    if not ids:
        return {"source": "pubmed", "query": query, "count": 0, "results": []}
    # 2) summary — detalları al
    ids_str = ",".join(ids)
    url_sum = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={ids_str}&retmode=json"
    status, body = _http_get(url_sum)
    if status != 200:
        return {"source": "pubmed", "error": body, "results": []}
    try:
        result = json.loads(body).get("result", {})
    except Exception as e:
        return {"source": "pubmed", "error": f"parse: {e}", "results": []}
    results = []
    for pmid in ids:
        r = result.get(pmid, {})
        if not r:
            continue
        results.append({
            "title": r.get("title", ""),
            "authors": r.get("sortfirstauthor", ""),
            "year": (r.get("pubdate") or "")[:4],
            "journal": r.get("source", ""),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "pmid": pmid,
        })
    return {"source": "pubmed", "query": query, "count": len(results), "results": results}


# ════════════════════════════════════════════════════════════════
# 5) SEC EDGAR — ABŞ korporativ maliyyə
# ════════════════════════════════════════════════════════════════
def sec_edgar_search(query: str, max_results: int = 5) -> dict:
    """
    SEC EDGAR Full-Text Search: efts.sec.gov
    Şirkət adı və ya CIK ilə son filing-lər.
    """
    q = urllib.parse.quote(f'"{query}"')
    url = f"https://efts.sec.gov/LATEST/search-index?q={q}&dateRange=custom&startdt=2024-01-01&forms=10-K,10-Q,8-K&hits={max_results}"
    status, body = _http_get(url, headers={"Accept": "application/json"})
    if status != 200:
        return {"source": "sec_edgar", "error": body, "results": []}
    try:
        data = json.loads(body)
    except Exception as e:
        return {"source": "sec_edgar", "error": f"parse: {e}", "results": []}
    hits = data.get("hits", {}).get("hits", [])
    results = []
    for h in hits[:max_results]:
        s = h.get("_source", {})
        results.append({
            "title": s.get("display_names", ["", "", ""])[0] + " — " + s.get("form", ""),
            "date": s.get("file_date", ""),
            "form": s.get("form", ""),
            "company": (s.get("display_names") or [""])[0],
            "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={s.get('ciks', [''])[0]}&type={s.get('form', '')}",
        })
    return {"source": "sec_edgar", "query": query, "count": len(results), "results": results}


# ════════════════════════════════════════════════════════════════
# 6) World Bank — qlobal iqtisadi
# ════════════════════════════════════════════════════════════════
def worldbank_search(query: str, max_results: int = 5) -> dict:
    """
    World Bank API: api.worldbank.org/v2/country
    Ölkələr və ya göstəricilər üzrə iqtisadi data.
    """
    q = urllib.parse.quote(query)
    # Suala uyğun ölkə tap
    url = f"https://api.worldbank.org/v2/country/{q}?format=json&per_page={max_results}"
    status, body = _http_get(url)
    if status != 200:
        return {"source": "worldbank", "error": body, "results": []}
    try:
        data = json.loads(body)
    except Exception as e:
        return {"source": "worldbank", "error": f"parse: {e}", "results": []}
    if not data or len(data) < 2 or not data[1]:
        # Indicator axtarışı
        url2 = f"https://api.worldbank.org/v2/indicator?format=json&per_page={max_results}"
        s, b = _http_get(url2 + f"&search={q}")
        if s == 200:
            try:
                d = json.loads(b)
                if d and len(d) > 1 and d[1]:
                    results = [{
                        "title": f"{x.get('name', '')} ({x.get('id', '')})",
                        "source_note": (x.get("sourceNote") or "")[:300],
                        "url": "https://data.worldbank.org/indicator/" + (x.get("id", "") or ""),
                    } for x in d[1][:max_results]]
                    return {"source": "worldbank", "query": query, "count": len(results), "results": results}
            except Exception:
                pass
        return {"source": "worldbank", "query": query, "count": 0, "results": []}
    results = []
    for c in data[1]:
        results.append({
            "title": f"{c.get('name', '')} ({c.get('id', '')})",
            "region": (c.get("region") or {}).get("value", ""),
            "income_level": (c.get("incomeLevel") or {}).get("value", ""),
            "capital": c.get("capitalCity", ""),
            "url": f"https://data.worldbank.org/country/{c.get('id', '')}",
        })
    return {"source": "worldbank", "query": query, "count": len(results), "results": results}


# ════════════════════════════════════════════════════════════════
# 7) GitHub Search — kod, layihələr
# ════════════════════════════════════════════════════════════════
def github_search(query: str, max_results: int = 5) -> dict:
    """
    GitHub Search API: api.github.com/search/repositories
    Repolar, kod, tendensiyalar.
    """
    q = urllib.parse.quote(f"{query} stars:>100")
    url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page={max_results}"
    status, body = _http_get(url, headers={"Accept": "application/vnd.github.v3+json"})
    if status != 200:
        return {"source": "github", "error": body, "results": []}
    try:
        data = json.loads(body)
    except Exception as e:
        return {"source": "github", "error": f"parse: {e}", "results": []}
    results = []
    for r in (data.get("items") or [])[:max_results]:
        results.append({
            "title": r.get("full_name", ""),
            "description": (r.get("description") or "")[:300],
            "stars": r.get("stargazers_count", 0),
            "language": r.get("language", ""),
            "url": r.get("html_url", ""),
            "topics": r.get("topics", [])[:5],
            "updated": r.get("updated_at", "")[:10],
        })
    return {"source": "github", "query": query, "count": len(results), "results": results}


# ════════════════════════════════════════════════════════════════
# 8) Hacker News — texnoloji müzakirələr
# ════════════════════════════════════════════════════════════════
def hackernews_search(query: str, max_results: int = 5) -> dict:
    """
    Hacker News Algolia Search: hn.algolia.com/api/v1/search
    Texnoloji xəbərlər və müzakirələr.
    """
    q = urllib.parse.quote(query)
    url = f"https://hn.algolia.com/api/v1/search?query={q}&hitsPerPage={max_results}"
    status, body = _http_get(url)
    if status != 200:
        return {"source": "hackernews", "error": body, "results": []}
    try:
        data = json.loads(body)
    except Exception as e:
        return {"source": "hackernews", "error": f"parse: {e}", "results": []}
    results = []
    for h in (data.get("hits") or [])[:max_results]:
        results.append({
            "title": h.get("title") or h.get("story_title", ""),
            "url": h.get("url") or h.get("story_url", ""),
            "points": h.get("points", 0),
            "comments": h.get("num_comments", 0),
            "author": h.get("author", ""),
            "created": h.get("created_at", "")[:10],
            "hn_url": f"https://news.ycombinator.com/item?id={h.get('objectID', '')}",
        })
    return {"source": "hackernews", "query": query, "count": len(results), "results": results}


# ════════════════════════════════════════════════════════════════
# 9) Wikidata — strukturlaşdırılmış bili (SPARQL)
# ════════════════════════════════════════════════════════════════
def wikidata_search(query: str, max_results: int = 5) -> dict:
    """
    Wikidata Search API: wikidata.org/w/api.php?action=wbsearchentities
    Strukturlaşdırılmış bili bazası.
    """
    q = urllib.parse.quote(query)
    url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={q}&language=en&limit={max_results}&format=json"
    status, body = _http_get(url)
    if status != 200:
        return {"source": "wikidata", "error": body, "results": []}
    try:
        data = json.loads(body)
    except Exception as e:
        return {"source": "wikidata", "error": f"parse: {e}", "results": []}
    results = []
    for r in (data.get("search") or [])[:max_results]:
        results.append({
            "title": r.get("label", ""),
            "description": (r.get("description") or "")[:200],
            "wikidata_id": r.get("id", ""),
            "url": f"https://www.wikidata.org/wiki/{r.get('id', '')}",
        })
    return {"source": "wikidata", "query": query, "count": len(results), "results": results}


# ════════════════════════════════════════════════════════════════
# 10) OpenCorporates — şirkət reyestri
# ════════════════════════════════════════════════════════════════
def opencorporates_search(query: str, max_results: int = 5) -> dict:
    """
    OpenCorporates API: api.opencorporates.com/v0.4/companies/search
    200M+ şirkət, 230+ jurisdiksiya.
    """
    q = urllib.parse.quote(query)
    url = f"https://api.opencorporates.com/v0.4/companies/search?q={q}&per_page={max_results}"
    status, body = _http_get(url, headers={"Accept": "application/json"})
    if status != 200:
        return {"source": "opencorporates", "error": body, "results": []}
    try:
        data = json.loads(body)
    except Exception as e:
        return {"source": "opencorporates", "error": f"parse: {e}", "results": []}
    results = []
    for c in (data.get("results", {}).get("companies") or [])[:max_results]:
        co = c.get("company", {})
        results.append({
            "title": co.get("name", ""),
            "jurisdiction": co.get("jurisdiction_code", ""),
            "company_number": co.get("company_number", ""),
            "status": co.get("current_status", ""),
            "url": co.get("opencorporates_url", ""),
            "registered_address": (co.get("registered_address_in_full") or "")[:200],
        })
    return {"source": "opencorporates", "query": query, "count": len(results), "results": results}


# ════════════════════════════════════════════════════════════════
# Elite sorğu koordinatoru
# ════════════════════════════════════════════════════════════════
ELITE_SOURCES = {
    "arxiv": ("Akademik preprintlər (AI, fizika, CS)", arxiv_search),
    "openalex": ("Bütün sahələr — 250M+ akademik iş", openalex_search),
    "semantic_scholar": ("AI/ML tədqiqat, sitat qrafı", semantic_scholar_search),
    "pubmed": ("Biotibbi, səhiyyə", pubmed_search),
    "sec_edgar": ("ABŞ korporativ maliyyə hesabatları", sec_edgar_search),
    "worldbank": ("Qlobal iqtisadi göstəricilər", worldbank_search),
    "github": ("Kod, layihə, tendensiyalar", github_search),
    "hackernews": ("Texnoloji müzakirələr", hackernews_search),
    "wikidata": ("Strukturlaşdırılmış bili", wikidata_search),
    "opencorporates": ("Şirkət reyestri (200M+)", opencorporates_search),
}


def elite_research(query: str, sources: list[str] | None = None, max_results: int = 3, parallel: bool = True) -> dict:
    """
    Elite mənbələrdən paralel/ardıcıl sorğu.
    sources=None → 4 sürətli mənbə (default, rate limit riski az).
    """
    if sources is None:
        sources = ["openalex", "arxiv", "github", "hackernews"]  # default — sürətli
    if parallel:
        import concurrent.futures
        out = {"query": query, "ts": datetime.now().isoformat(timespec="seconds"), "sources": {}}
        # 3 worker ilə paralel (rate limit riskini azaldır)
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            futures = {}
            for s in sources:
                if s in ELITE_SOURCES:
                    _, fn = ELITE_SOURCES[s]
                    futures[ex.submit(fn, query, max_results)] = s
            for f in concurrent.futures.as_completed(futures, timeout=60):
                s = futures[f]
                try:
                    out["sources"][s] = f.result()
                except Exception as e:
                    out["sources"][s] = {"source": s, "error": str(e), "results": []}
        return out
    else:
        out = {"query": query, "ts": datetime.now().isoformat(timespec="seconds"), "sources": {}}
        for s in sources:
            if s in ELITE_SOURCES:
                _, fn = ELITE_SOURCES[s]
                try:
                    out["sources"][s] = fn(query, max_results)
                except Exception as e:
                    out["sources"][s] = {"source": s, "error": str(e), "results": []}
        return out


def available_sources() -> list[str]:
    return list(ELITE_SOURCES.keys())


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "artificial intelligence"
    print(f"Elite sorğu: {q}")
    r = elite_research(q, max_results=3, parallel=True)
    for s, data in r.get("sources", {}).items():
        n = data.get("count", 0)
        err = data.get("error")
        if err:
            print(f"  [{s}] ✖ xəta: {err[:80]}")
        else:
            print(f"  [{s}] ✓ {n} nəticə")
    print()
    print(json.dumps(r, ensure_ascii=False, indent=2)[:2000])
