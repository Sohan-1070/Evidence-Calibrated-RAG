"""
Evidence Gathering Modules for the 7-Stage Factual Verification Pipeline.

Provides real, targeted backend evidence retrieval across all 6 evidence tiers:
Stage 1: Official Sources (.gov, WHO, agencies, official documentation)
Stage 2: Primary Evidence (original reports, research papers, datasets, PDFs)
Stage 3: Reference Sources (Wikipedia, encyclopedias, educational websites)
Stage 4: Academic Sources (peer-reviewed papers, universities, expert institutions)
Stage 5: Reputable News (independent reporting and recent developments)
Stage 6: Community Sources (Reddit, Quora, blogs - leads only)
"""

import os
import re
import json
from html import unescape
from datetime import datetime
from urllib.parse import quote_plus, urlparse, parse_qs, urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from typing import List, Dict, Optional, Any

try:
    from .claim_ledger import EvidenceItem
except ImportError:
    from claim_ledger import EvidenceItem


# ============================================================
# HTTP & SEARCH HELPERS
# ============================================================

DEFAULT_TIMEOUT = 7.0
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()


def _safe_fetch(url: str, headers: Optional[Dict[str, str]] = None, timeout: float = DEFAULT_TIMEOUT) -> Optional[bytes]:
    req_headers = {"User-Agent": USER_AGENT}
    if headers:
        req_headers.update(headers)
    req = Request(url, headers=req_headers)
    try:
        with urlopen(req, timeout=timeout) as response:
            return response.read()
    except Exception as e:
        return None


def _clean_text(html_text: str) -> str:
    if not html_text:
        return ""
    text = re.sub(r"<[^>]+>", " ", html_text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_ddg_url(href: str) -> str:
    if not href:
        return ""
    href = unescape(href)
    try:
        parsed = urlparse(href)
        params = parse_qs(parsed.query)
        if "uddg" in params:
            return unescape(params["uddg"][0])
    except Exception:
        pass
    if href.startswith("//"):
        return "https:" + href
    return href


def _duckduckgo_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    query = re.sub(r"\s+", " ", str(query or "")).strip()
    if not query:
        return []

    results = []
    seen_urls = set()

    # 1. Try DuckDuckGo Instant Answer API (robust JSON without HTML bot challenges)
    api_url = "https://api.duckduckgo.com/?q=" + quote_plus(query) + "&format=json&no_html=1"
    raw_json = _safe_fetch(api_url, timeout=DEFAULT_TIMEOUT)
    if raw_json:
        try:
            data = json.loads(raw_json.decode("utf-8", errors="replace"))
            if data.get("AbstractText") and data.get("AbstractURL"):
                u = data.get("AbstractURL")
                seen_urls.add(u)
                results.append({
                    "title": data.get("Heading") or query,
                    "url": u,
                    "snippet": data.get("AbstractText")
                })
            for topic in data.get("RelatedTopics", []):
                if len(results) >= max_results:
                    break
                if isinstance(topic, dict) and "Text" in topic and "FirstURL" in topic:
                    u = topic.get("FirstURL")
                    if u not in seen_urls:
                        seen_urls.add(u)
                        results.append({
                            "title": topic.get("Text")[:65],
                            "url": u,
                            "snippet": topic.get("Text")
                        })
                elif isinstance(topic, dict) and "Topics" in topic:
                    for sub in topic.get("Topics", []):
                        if len(results) >= max_results:
                            break
                        if isinstance(sub, dict) and "Text" in sub and "FirstURL" in sub:
                            u = sub.get("FirstURL")
                            if u not in seen_urls:
                                seen_urls.add(u)
                                results.append({
                                    "title": sub.get("Text")[:65],
                                    "url": u,
                                    "snippet": sub.get("Text")
                                })
            if len(results) >= max_results:
                return results[:max_results]
        except Exception:
            pass

    # 2. DuckDuckGo Lite via POST (High reliability, never blocked by bot challenge, full snippets)
    try:
        lite_data = urlencode({"q": query}).encode("utf-8")
        req = Request(
            "https://lite.duckduckgo.com/lite/",
            data=lite_data,
            headers={"User-Agent": USER_AGENT}
        )
        with urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            lite_html = resp.read().decode("utf-8", errors="replace")

        pattern = (
            r'<a[^>]+href=[\'"]([^\'"]+)[\'"][^>]+class=[\'"]result-link[\'"][^>]*>(.*?)</a>|'
            r'<a[^>]+class=[\'"]result-link[\'"][^>]+href=[\'"]([^\'"]+)[\'"][^>]*>(.*?)</a>'
        )
        links_raw = re.findall(pattern, lite_html, flags=re.I | re.S)
        snippets_raw = re.findall(r'<td[^>]+class=[\'"]result-snippet[\'"][^>]*>(.*?)</td>', lite_html, flags=re.I | re.S)

        for idx, match in enumerate(links_raw):
            if len(results) >= max_results:
                break
            raw_url = match[0] or match[2]
            clean_url = _clean_ddg_url(raw_url)
            raw_title = match[1] or match[3]
            title = _clean_text(raw_title)
            snip = ""
            if idx < len(snippets_raw):
                snip = _clean_text(snippets_raw[idx])
            if title and clean_url and clean_url not in seen_urls:
                seen_urls.add(clean_url)
                results.append({
                    "title": title,
                    "url": clean_url,
                    "snippet": snip
                })
        if results:
            return results[:max_results]
    except Exception:
        pass

    # 3. Fallback to HTML search
    url = "https://html.duckduckgo.com/html/?q=" + quote_plus(query)
    raw_html = _safe_fetch(url, timeout=DEFAULT_TIMEOUT)
    if not raw_html:
        return results
    html = raw_html.decode("utf-8", errors="replace")

    link_matches = re.findall(
        r'<a[^>]+class=["\']result__a["\'][^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        html,
        flags=re.I | re.S
    )
    for href, raw_title in link_matches[:max_results]:
        if len(results) >= max_results:
            break
        title = _clean_text(raw_title)
        clean_url = _clean_ddg_url(href)
        pos = html.find(raw_title)
        snippet = ""
        if pos >= 0:
            tail = html[pos:pos + 4000]
            sm = re.search(r'class=["\']result__snippet["\'][^>]*>(.*?)</', tail, flags=re.I | re.S)
            if sm:
                snippet = _clean_text(sm.group(1))
        if title and clean_url and clean_url not in seen_urls:
            seen_urls.add(clean_url)
            results.append({
                "title": title,
                "url": clean_url,
                "snippet": snippet
            })
    return results[:max_results]


def _tavily_search(query: str, max_results: int = 5, include_domains: Optional[List[str]] = None, topic: str = "general") -> List[Dict[str, Any]]:
    if not TAVILY_API_KEY:
        return []
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "topic": topic if topic in {"general", "news"} else "general",
        "max_results": max(1, min(max_results, 8)),
        "include_answer": False,
        "include_raw_content": False,
    }
    if include_domains:
        payload["include_domains"] = list(include_domains)

    try:
        req = Request(
            "https://api.tavily.com/search",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
            method="POST"
        )
        with urlopen(req, timeout=DEFAULT_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
        results = []
        for item in data.get("results", []):
            results.append({
                "title": str(item.get("title", "")).strip(),
                "url": str(item.get("url", "")).strip(),
                "snippet": str(item.get("content") or item.get("snippet") or "").strip(),
                "published_date": item.get("published_date")
            })
        return results
    except Exception:
        return []


# ============================================================
# STAGE 1: OFFICIAL SOURCES (.gov, WHO, agencies, official documentation)
# ============================================================

OFFICIAL_ENTITY_DOMAINS = {
    # Automotive & Mobility
    "tesla": "tesla.com",
    "porsche": "porsche.com",
    "ferrari": "ferrari.com",
    "lamborghini": "lamborghini.com",
    "bmw": "bmw.com",
    "mercedes": "mercedes-benz.com",
    "audi": "audi.com",
    "ford": "ford.com",
    "toyota": "toyota.com",
    "honda": "honda.com",
    "hyundai": "hyundai.com",
    "volkswagen": "vw.com",
    "chevrolet": "chevrolet.com",
    "bugatti": "bugatti.com",
    "mclaren": "mclaren.com",
    "lucid": "lucidmotors.com",
    "rivian": "rivian.com",
    # Consumer Tech & Electronics
    "apple": "apple.com",
    "iphone": "apple.com",
    "ipad": "apple.com",
    "macbook": "apple.com",
    "microsoft": "microsoft.com",
    "windows": "microsoft.com",
    "xbox": "xbox.com",
    "surface": "microsoft.com",
    "google": "google.com",
    "pixel": "store.google.com",
    "android": "android.com",
    "sony": "sony.com",
    "playstation": "playstation.com",
    "ps5": "playstation.com",
    "samsung": "samsung.com",
    "galaxy": "samsung.com",
    "nvidia": "nvidia.com",
    "geforce": "nvidia.com",
    "rtx": "nvidia.com",
    "intel": "intel.com",
    "amd": "amd.com",
    "qualcomm": "qualcomm.com",
    "asus": "asus.com",
    "dell": "dell.com",
    "hp": "hp.com",
    "lenovo": "lenovo.com",
    # AI & Cloud Platforms
    "openai": "openai.com",
    "chatgpt": "openai.com",
    "anthropic": "anthropic.com",
    "claude": "anthropic.com",
    "amazon": "amazon.com",
    "aws": "aws.amazon.com",
    "meta": "meta.com",
    "netflix": "netflix.com",
    # Sports Governing Federations & Leagues
    "fifa": "fifa.com",
    "icc": "icc-cricket.com",
    "bcci": "bcci.tv",
    "olympics": "olympics.com",
    "ioc": "olympics.com",
    "uefa": "uefa.com",
    "nba": "nba.com",
    "f1": "formula1.com",
    "formula 1": "formula1.com",
    "wimbledon": "wimbledon.com",
    # Science, Standards, Space & Health
    "isro": "isro.gov.in",
    "nasa": "nasa.gov",
    "spacex": "spacex.com",
    "who": "who.int",
    "cdc": "cdc.gov",
    "nih": "nih.gov",
    "pib": "pib.gov.in",
    "un": "un.org",
    "cern": "home.cern",
    "esa": "esa.int",
    "nist": "nist.gov",
    "bipm": "bipm.org",
    "nobel": "nobelprize.org",
    "pubchem": "pubchem.ncbi.nlm.nih.gov",
    "imd": "mausam.imd.gov.in",
    # Global Governance, Regulators & Public Bodies
    "rbi": "rbi.org.in",
    "sebi": "sebi.gov.in",
    "world bank": "worldbank.org",
    "imf": "imf.org",
    "unesco": "unesco.org",
    "wto": "wto.org",
    "upsc": "upsc.gov.in",
    "nta": "nta.ac.in",
    "drdo": "drdo.gov.in",
    # Open-Source Foundations & Technical Standards
    "python": "python.org",
    "linux": "kernel.org",
    "rust": "rust-lang.org",
    "golang": "go.dev",
    "w3c": "w3.org",
    "ieee": "ieee.org",
    # Universities & Academic Institutions
    "srm": "srmist.edu.in",
    "srmist": "srmist.edu.in",
    "mit": "mit.edu",
    "stanford": "stanford.edu",
    "harvard": "harvard.edu",
    "oxford": "ox.ac.uk",
    "cambridge": "cam.ac.uk",
    "iit": "iitd.ac.in",
    "iisc": "iisc.ac.in",
    "aiims": "aiims.edu",
    "caltech": "caltech.edu",
    "berkeley": "berkeley.edu"
}

def is_authoritative_first_party_domain(domain: str, target_domain: Optional[str] = None) -> bool:
    """Universally detects if a domain is a verified first-party, government, scientific, or academic Tier-1 authority."""
    if not domain:
        return False
    d = domain.lower()
    if target_domain and target_domain in d:
        return True
    # Government & sovereign agencies worldwide
    if any(suffix in d for suffix in [".gov", ".gov.in", ".gov.uk", ".gov.au", ".gov.ca", ".nic.in", ".mil", ".gob."]):
        return True
    # International & treaty organizations
    if any(org in d for org in [".int", "who.int", "un.org", "unesco.org", "worldbank.org", "imf.org", "wto.org", "esa.int", "home.cern", "cern.ch", "iso.org", "w3.org"]):
        return True
    # Accredited higher education & research institutions
    if any(edu in d for edu in [".edu", ".edu.in", ".ac.uk", ".edu.au"]):
        return True
    # National standards, physics, chemical & medical repositories
    if any(sci in d for sci in ["nist.gov", "bipm.org", "nobelprize.org", "ncbi.nlm.nih.gov", "pubchem.ncbi"]):
        return True
    # Global sports federations
    if any(sport in d for sport in ["fifa.com", "icc-cricket.com", "olympics.com", "ioc.org", "uefa.com", "nba.com", "formula1.com", "bcci.tv"]):
        return True
    # Major open-source & technical project anchors
    if any(tech in d for tech in ["python.org", "kernel.org", "rust-lang.org", "go.dev", "linuxfoundation.org"]):
        return True
    return False

def _detect_official_domain(query: str) -> Optional[Any]:
    q_lower = query.lower()
    for entity, domain in OFFICIAL_ENTITY_DOMAINS.items():
        if re.search(r"\b" + re.escape(entity) + r"\b", q_lower):
            return entity, domain
    return None

def _extract_clean_entity_keywords(query: str, entity_name: str) -> str:
    stop_words = {
        "how", "much", "does", "do", "did", "is", "are", "was", "were", "what",
        "can", "will", "would", "could", "should", "tell", "me", "about",
        "a", "an", "the", "in", "of", "for", "to", "on", "at", "by", "costs",
        "cost", "priced", "pricing", "gap", "gaps", "vs", "versus"
    }
    clean = re.sub(r"[^\w\s-]", " ", query.lower()).strip()
    words = [w for w in clean.split() if w not in stop_words]
    return " ".join(words) if words else clean

def search_stage_1_official(query: str, max_results: int = 5) -> List[EvidenceItem]:
    """
    Stage 1: Official Sources & Universal First-Party Ground Truth.
    Retrieves from government agencies (.gov, WHO, UN), accredited universities (.edu, .ac.uk),
    national scientific repositories (NIST, BIPM, PubChem), sports federations, or official
    first-party manufacturer/organizational portals across all query domains.
    """
    clean_q = re.sub(r"[^\w\s-]", " ", query).strip()
    q_lower = query.lower()
    matched_entity = _detect_official_domain(query)
    raw_results = []
    seen_urls = set()

    if matched_entity:
        entity_name, target_domain = matched_entity
        keywords = _extract_clean_entity_keywords(query, entity_name)

        # 1. First-party domain search via Tavily if configured
        if TAVILY_API_KEY:
            t_res = _tavily_search(keywords, max_results=max_results, include_domains=[target_domain])
            for r in t_res:
                u = r.get("url", "")
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    raw_results.append(r)

        # 2. First-party site search via DuckDuckGo Lite
        if len(raw_results) < max_results:
            site_query = f"site:{target_domain} {keywords}"
            ddg_res = _duckduckgo_search(site_query, max_results=max_results - len(raw_results))
            for r in ddg_res:
                u = r.get("url", "")
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    raw_results.append(r)

        # 3. Topic-specific deep queries across all domains:
        # A) Rules, Policy, Eligibility, Criteria, Admissions
        is_policy = any(w in q_lower for w in ["criteria", "eligibility", "admission", "requirements", "rules", "policy", "guidelines", "syllabus", "attendance"])
        if is_policy and len(raw_results) < max_results:
            spec_query = f"site:{target_domain} {keywords} official guidelines requirements"
            for r in _duckduckgo_search(spec_query, max_results=2):
                if r.get("url") and r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    raw_results.append(r)

        # B) Records, Winners, Champions, Founding, History, Leadership
        is_record = any(w in q_lower for w in ["winner", "champion", "record", "release date", "founded", "history", "established", "headquarters", "ceo", "director", "president"])
        if is_record and len(raw_results) < max_results:
            rec_query = f"site:{target_domain} {keywords} official record history"
            for r in _duckduckgo_search(rec_query, max_results=2):
                if r.get("url") and r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    raw_results.append(r)

        # C) Science, Specs, Capabilities, Pricing, Metrics
        is_specs_or_pricing = any(w in q_lower for w in ["price", "cost", "how much", "msrp", "rate", "specs", "speed", "power", "horsepower", "boiling point", "constant", "formula"])
        if is_specs_or_pricing and len(raw_results) < max_results:
            spec_query = f"site:{target_domain} {keywords} specifications"
            for r in _duckduckgo_search(spec_query, max_results=2):
                if r.get("url") and r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    raw_results.append(r)

        # 4. Supplementary official query if site: query returned few results
        if len(raw_results) < 2:
            broad_query = f"{entity_name} {keywords} official website documentation"
            broad_res = _duckduckgo_search(broad_query, max_results=max_results - len(raw_results))
            for r in broad_res:
                u = r.get("url", "")
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    raw_results.append(r)

    else:
        # Universal authoritative portals across all topics: Government, Science, Health, Universities
        official_query = f"{clean_q} site:.gov OR site:.gov.in OR site:.gov.uk OR site:.edu OR site:who.int OR site:un.org OR site:isro.gov.in OR site:nih.gov OR site:nist.gov"
        if TAVILY_API_KEY:
            domains = ["gov.in", "who.int", "pib.gov.in", "isro.gov.in", "nih.gov", "cdc.gov", "un.org", "nist.gov", "edu"]
            raw_results = _tavily_search(clean_q, max_results=max_results, include_domains=domains)

        if not raw_results:
            raw_results = _duckduckgo_search(official_query, max_results=max_results)

    items = []
    for idx, res in enumerate(raw_results, 1):
        url = res.get("url", "")
        domain = EvidenceItem._extract_domain(url)
        target_dom = matched_entity[1] if matched_entity else None
        is_official = is_authoritative_first_party_domain(domain, target_dom)

        cat_name = "Official First-Party Documentation" if (matched_entity and is_official) else ("Official Government / Agency / Institution" if is_official else "Authoritative Primary Reference")

        items.append(
            EvidenceItem(
                evidence_id=f"stg1_{idx}",
                stage=1,
                title=res.get("title", "Official Record"),
                url_or_ref=url,
                snippet=res.get("snippet", ""),
                domain=domain,
                published_date=res.get("published_date"),
                authority_tier=1 if is_official else 2,
                is_community_lead=False,
                extra_metadata={"source_category": cat_name, "is_official": is_official}
            )
        )
    return items


# ============================================================
# STAGE 2: PRIMARY EVIDENCE (Original Reports, Datasets, PDFs)
# ============================================================

def search_stage_2_primary(
    query: str,
    max_results: int = 5,
    pdf_path: Optional[str] = None,
    offline_chunks: Optional[List[Dict[str, Any]]] = None
) -> List[EvidenceItem]:
    """
    Retrieve from local uploaded PDF/document chunks, or search external primary reports/datasets/PDFs.
    """
    items = []

    # Path A: Local Document / PDF is active in ECRAG
    if offline_chunks:
        # Search chunks for matching keywords/terms
        words = set(re.findall(r"\w{4,}", query.lower()))
        scored_chunks = []
        for ch in offline_chunks:
            text = ch.get("text", "")
            page = ch.get("page", 1)
            text_lower = text.lower()
            score = sum(1 for w in words if w in text_lower)
            if score > 0:
                scored_chunks.append((score, page, text))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        for idx, (score, page, text) in enumerate(scored_chunks[:max_results], 1):
            doc_name = os.path.basename(pdf_path) if pdf_path else "active_document.pdf"
            items.append(
                EvidenceItem(
                    evidence_id=f"stg2_doc_{idx}",
                    stage=2,
                    title=f"{doc_name} (Page {page})",
                    url_or_ref=f"doc://{doc_name}#page={page}",
                    snippet=text[:500],
                    domain="primary-document",
                    authority_tier=1,
                    is_community_lead=False,
                    extra_metadata={"page": page, "match_score": score}
                )
            )
        if items:
            return items

    # Path B: External Primary Documents / Reports / Datasets
    clean_q = re.sub(r"[^\w\s-]", " ", query).strip()
    primary_query = f"{clean_q} filetype:pdf OR \"technical report\" OR \"primary dataset\" OR \"final report\""
    raw_results = _duckduckgo_search(primary_query, max_results=max_results)

    for idx, res in enumerate(raw_results, 1):
        items.append(
            EvidenceItem(
                evidence_id=f"stg2_web_{idx}",
                stage=2,
                title=res.get("title", "Primary Report / Publication"),
                url_or_ref=res.get("url", ""),
                snippet=res.get("snippet", ""),
                domain=EvidenceItem._extract_domain(res.get("url", "")),
                authority_tier=2,
                is_community_lead=False,
                extra_metadata={"source_category": "Primary Evidence / Document"}
            )
        )
    return items


# ============================================================
# STAGE 3: REFERENCE SOURCES (Wikipedia, Encyclopedias, Educational)
# ============================================================

def search_stage_3_reference(query: str, max_results: int = 4) -> List[EvidenceItem]:
    """
    Search Wikipedia public REST API and encyclopedia reference platforms.
    """
    items = []
    clean_q = re.sub(r"[^\w\s-]", " ", query).strip()

    # 1. Wikipedia Search API
    queries_to_try = [clean_q]
    stop = {'does', 'a', 'an', 'the', 'gap', 'gaps', 'what', 'is', 'are', 'in', 'can', 'will', 'do', 'how', 'why', 'who', 'tell', 'me', 'about'}
    clean_words = [w for w in re.findall(r'\b\w+\b', clean_q.lower()) if w not in stop]
    if clean_words and ' '.join(clean_words) != clean_q.lower():
        queries_to_try.append(' '.join(clean_words))

    for q_attempt in queries_to_try:
        wiki_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote_plus(q_attempt)}&format=json&utf8=1"
        raw_bytes = _safe_fetch(wiki_url, timeout=DEFAULT_TIMEOUT)
        if raw_bytes:
            try:
                data = json.loads(raw_bytes.decode("utf-8", errors="replace"))
                search_items = data.get("query", {}).get("search", [])
                for idx, entry in enumerate(search_items[:max_results], len(items) + 1):
                    title = entry.get("title", "")
                    snippet = _clean_text(entry.get("snippet", ""))
                    pageid = entry.get("pageid", "")
                    url = f"https://en.wikipedia.org/wiki/{quote_plus(title.replace(' ', '_'))}"
                    items.append(
                        EvidenceItem(
                            evidence_id=f"stg3_wiki_{idx}",
                            stage=3,
                            title=f"Wikipedia: {title}",
                            url_or_ref=url,
                            snippet=snippet,
                            domain="en.wikipedia.org",
                            authority_tier=3,
                            is_community_lead=False,
                            extra_metadata={"pageid": pageid, "source_category": "Encyclopedia"}
                        )
                    )
            except Exception:
                pass
        if len(items) >= max_results:
            break

    # 2. If Wikipedia search yielded few results, fallback/supplement with Britannica or .edu reference
    if len(items) < max_results:
        ref_query = f"{clean_q} site:britannica.com OR site:en.wikipedia.org OR site:.edu"
        raw_results = _duckduckgo_search(ref_query, max_results=max_results - len(items))
        for idx, res in enumerate(raw_results, len(items) + 1):
            items.append(
                EvidenceItem(
                    evidence_id=f"stg3_ref_{idx}",
                    stage=3,
                    title=res.get("title", "Reference Article"),
                    url_or_ref=res.get("url", ""),
                    snippet=res.get("snippet", ""),
                    domain=EvidenceItem._extract_domain(res.get("url", "")),
                    authority_tier=3,
                    is_community_lead=False,
                    extra_metadata={"source_category": "Reference / Encyclopedia"}
                )
            )

    return items


# ============================================================
# STAGE 4: ACADEMIC SOURCES (Peer-Reviewed, ArXiv, Universities)
# ============================================================

def search_stage_4_academic(query: str, max_results: int = 4) -> List[EvidenceItem]:
    """
    Search ArXiv public repository API and academic publishers (.edu, pubmed, biorxiv).
    """
    items = []
    clean_q = re.sub(r"[^\w\s-]", " ", query).strip()

    # 1. Query ArXiv Atom Feed
    arxiv_url = f"http://export.arxiv.org/api/query?search_query=all:{quote_plus(clean_q)}&start=0&max_results={max_results}"
    raw_xml = _safe_fetch(arxiv_url, timeout=DEFAULT_TIMEOUT)
    if raw_xml:
        try:
            root = ET.fromstring(raw_xml)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for idx, entry in enumerate(root.findall("atom:entry", ns)[:max_results], 1):
                title_elem = entry.find("atom:title", ns)
                summary_elem = entry.find("atom:summary", ns)
                published_elem = entry.find("atom:published", ns)
                id_elem = entry.find("atom:id", ns)

                title = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else "Academic Preprint"
                summary = summary_elem.text.strip().replace("\n", " ") if summary_elem is not None and summary_elem.text else ""
                published = published_elem.text.strip() if published_elem is not None and published_elem.text else None
                url = id_elem.text.strip() if id_elem is not None and id_elem.text else "https://arxiv.org"

                items.append(
                    EvidenceItem(
                        evidence_id=f"stg4_arxiv_{idx}",
                        stage=4,
                        title=f"ArXiv: {title}",
                        url_or_ref=url,
                        snippet=summary[:500],
                        domain="arxiv.org",
                        published_date=published[:10] if published else None,
                        authority_tier=2,
                        is_community_lead=False,
                        extra_metadata={"source_category": "Peer-Reviewed / Academic"}
                    )
                )
        except Exception:
            pass

    # 2. Supplement with university or pubmed domains via DuckDuckGo
    if len(items) < max_results:
        acad_query = f"{clean_q} site:arxiv.org OR site:ncbi.nlm.nih.gov OR site:biorxiv.org OR site:.edu"
        raw_results = _duckduckgo_search(acad_query, max_results=max_results - len(items))
        for idx, res in enumerate(raw_results, len(items) + 1):
            items.append(
                EvidenceItem(
                    evidence_id=f"stg4_acad_{idx}",
                    stage=4,
                    title=res.get("title", "Academic Research"),
                    url_or_ref=res.get("url", ""),
                    snippet=res.get("snippet", ""),
                    domain=EvidenceItem._extract_domain(res.get("url", "")),
                    authority_tier=2,
                    is_community_lead=False,
                    extra_metadata={"source_category": "Academic / Institutional"}
                )
            )

    return items


# ============================================================
# STAGE 5: REPUTABLE NEWS (Independent Reporting, Google News RSS)
# ============================================================

def search_stage_5_news(query: str, max_results: int = 5) -> List[EvidenceItem]:
    """
    Search Google News RSS feed for recent independent reporting.
    """
    items = []
    clean_q = re.sub(r"[^\w\s-]", " ", query).strip()
    news_url = f"https://news.google.com/rss/search?q={quote_plus(clean_q)}&hl=en-IN&gl=IN&ceid=IN:en"
    raw_xml = _safe_fetch(news_url, timeout=DEFAULT_TIMEOUT)

    if raw_xml:
        try:
            root = ET.fromstring(raw_xml)
            for idx, item in enumerate(root.findall(".//item")[:max_results], 1):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                description = (item.findtext("description") or "").strip()
                pub_date = (item.findtext("pubDate") or "").strip()
                source_elem = item.find("source")
                source_name = source_elem.text.strip() if source_elem is not None and source_elem.text else ""

                clean_desc = _clean_text(description)
                domain = EvidenceItem._extract_domain(link)
                items.append(
                    EvidenceItem(
                        evidence_id=f"stg5_news_{idx}",
                        stage=5,
                        title=f"{source_name}: {title}" if source_name else title,
                        url_or_ref=link,
                        snippet=clean_desc,
                        domain=domain,
                        published_date=pub_date,
                        authority_tier=3,
                        is_community_lead=False,
                        extra_metadata={"publisher": source_name, "source_category": "Independent News"}
                    )
                )
        except Exception:
            pass

    # Fallback to web search if RSS returned empty
    if not items:
        raw_results = _duckduckgo_search(f"{clean_q} news reporting latest", max_results=max_results)
        for idx, res in enumerate(raw_results, 1):
            items.append(
                EvidenceItem(
                    evidence_id=f"stg5_fallback_{idx}",
                    stage=5,
                    title=res.get("title", "News Report"),
                    url_or_ref=res.get("url", ""),
                    snippet=res.get("snippet", ""),
                    domain=EvidenceItem._extract_domain(res.get("url", "")),
                    authority_tier=3,
                    is_community_lead=False,
                    extra_metadata={"source_category": "News"}
                )
            )

    return items


# ============================================================
# STAGE 6: COMMUNITY SOURCES (Reddit, Quora, Blogs - Leads Only)
# ============================================================

def search_stage_6_community(query: str, max_results: int = 4) -> List[EvidenceItem]:
    """
    Search community forums and discussions (Reddit, Quora, Medium).
    Strict constraint: Marked as leads only, never authoritative proof!
    """
    clean_q = re.sub(r"[^\w\s-]", " ", query).strip()
    comm_query = f"{clean_q} site:reddit.com OR site:quora.com OR site:medium.com"
    raw_results = _duckduckgo_search(comm_query, max_results=max_results)

    items = []
    for idx, res in enumerate(raw_results, 1):
        items.append(
            EvidenceItem(
                evidence_id=f"stg6_comm_{idx}",
                stage=6,
                title=f"Community Lead: {res.get('title', 'Forum Discussion')}",
                url_or_ref=res.get("url", ""),
                snippet=res.get("snippet", ""),
                domain=EvidenceItem._extract_domain(res.get("url", "")),
                authority_tier=4,
                is_community_lead=True,
                extra_metadata={
                    "source_category": "Community / Discussion",
                    "note": "LEAD ONLY: Never authoritative proof without independent corroboration."
                }
            )
        )
    return items
