"""
Lõi Reels View Scanner — viết thẳng logic của app.py vào tool.

Luồng (giống app.py):
  get_pfbid(page_id): GET facebook.com/<page_id> -> cắt node id 'owner_reels'
  get_view(pfbid):    POST graphql -> JSON 10 reel đầu
  scan_page(page_id): nối 2 bước + parse ra view / mô tả / thumbnail.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import requests


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
@dataclass
class Reel:
    video_id: str = ""
    description: str = ""
    views_text: str = ""       # "219K"
    views_num: int = 0          # 219000
    thumbnail: str = ""
    url: str = ""
    created: int = 0
    duration_s: float = 0.0


@dataclass
class PageResult:
    page_id: str = ""
    author: str = ""
    node_id: str = ""
    ok: bool = True
    error: str = ""
    reels: list[Reel] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Bước 1: page_id -> node id reels (owner_reels)  [logic app.py: get_pfbid]
# ---------------------------------------------------------------------------
def cut_string(string: str, start: str, end: str) -> str:
    return string.split(start)[1].split(end)[0]


def get_pfbid(page_id: str, timeout: int = 30) -> str:
    url = f"https://www.facebook.com/{page_id}"
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'dpr': '1',
        'priority': 'u=0, i',
        'sec-ch-prefers-color-scheme': 'light',
        'sec-ch-ua': '"Not;A=Brand";v="8", "Chromium";v="150", "Microsoft Edge";v="150"',
        'sec-ch-ua-full-version-list': '"Not;A=Brand";v="8.0.0.0", "Chromium";v="150.0.7871.115", "Microsoft Edge";v="150.0.4078.65"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-model': '""',
        'sec-ch-ua-platform': '"Windows"',
        'sec-ch-ua-platform-version': '"10.0.0"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0',
        'viewport-width': '1162',
        'Cookie': 'datr=M21caiohl8GXrQtHeKqsz8xs; sb=M21cakGEXPH-rOSfHTQte9Ti; wd=1162x922; fr=1zAFgKbq8NwYRjKJ5.AWcRutA3EkDtZvz1J4V0hkF8gH5c3d-4Ao1jN4vx_XGTUW4OpUc.BqWD1W..AAA.0.0.BqWD1W.AWfzut87we3d2X857fsHBDdsuVk; ps_l=1; ps_n=1'
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    try:
        return cut_string(response.text, '[{"tab_key":"owner_reels","id":"', '"')
    except IndexError:
        raise ValueError(
            "Không tìm thấy node id reels trên trang Page "
            "(ID sai, Page không có reels, hoặc cookie/token hết hạn)."
        )


# ---------------------------------------------------------------------------
# Bước 2: node id -> JSON reels  [logic app.py: get_view]
# ---------------------------------------------------------------------------
def get_view(pfbid: str, timeout: int = 30) -> str:
    url = "https://www.facebook.com/api/graphql/"
    variables = '{"count":10,"renderLocation":null,"scale":1,"useDefaultActor":false,"id":"' + pfbid + '","__relay_internal__pv__FBReels_deprecate_short_form_video_context_gkrelayprovider":false,"__relay_internal__pv__FBReelsMediaFooter_comet_enable_reels_ads_gkrelayprovider":true,"__relay_internal__pv__FBUnifiedVideoMediaContentContainer_comet_reels_video_footer_defer_loading_gkrelayprovider":false,"__relay_internal__pv__FBUnifiedVideoMediaContentContainer_comet_video_document_picture_in_picture_gkrelayprovider":false,"__relay_internal__pv__FBUnifiedVideoMediaContentContainer_enable_chapters_pill_gkrelayprovider":false,"__relay_internal__pv__ShouldEnableBakedInTextUnifiedVideorelayprovider":false,"__relay_internal__pv__FBUnifiedVideoMediaHeaderControls_enable_chapters_pill_gkrelayprovider":false,"__relay_internal__pv__FBUnifiedVideoMediaFooter_comet_enable_reels_ads_gkrelayprovider":true,"__relay_internal__pv__FBUnifiedVideoMediaFooter_enable_meta_ai_pill_gkrelayprovider":false,"__relay_internal__pv__FBUnifiedVideoMediaFooter_enable_ai_embodiment_chat_pill_gkrelayprovider":false,"__relay_internal__pv__FBUnifiedVideoMediaFooter_enable_group_character_ai_info_pill_gkrelayprovider":true,"__relay_internal__pv__FBUnifiedVideoMediaFooter_enable_video_augment_pills_gkrelayprovider":false,"__relay_internal__pv__FBUnifiedVideoFeedbackBar_comet_reels_save_button_gkrelayprovider":false,"__relay_internal__pv__usePushPipEngagementCounts_comet_video_document_picture_in_picture_gkrelayprovider":false,"__relay_internal__pv__FBReels_enable_view_dubbed_audio_type_gkrelayprovider":false,"__relay_internal__pv__FBUnifiedVideoMenu_fb_reels_ranking_debug_tool_gkrelayprovider":false}'
    payload = {
        "av": "0",
        "__aaid": "0",
        "__user": "0",
        "__a": "1",
        "__req": "e",
        "__hs": "20653.HYP:comet_loggedout_pkg.2.1...0",
        "dpr": "1",
        "__ccg": "EXCELLENT",
        "__rev": "1043435019",
        "__s": "elfi2e:bz9v98:1w19pc",
        "__hsi": "7664120732654396884",
        "__dyn": "7xeUmwlEnwn8yEqxemh0no6u5U4e1Nxt3odEc8co2qwJyE24wJwpUe8hw47w5nCwjE1EEbbwto2awgo9oO0n24oaEd82lwv89k2C1FwnE6a0D85m1mzXwae4UaEW2a0CEbrwmEe85nxm16wSwsFo8o11E5C2-azo7u1qwPwbS16xi4UdUcobUak0KU6O1fxC13G486S2m1tG2O7E5y0jWfw3roqwRy-78",
        "__csr": "hJWAuPcuWJpcCCdlyaRHKgl7NFeWZrWMEwxdin9FblqrRVl5QZ8HjiBjtWjHqAGBDILWQHYzOF4Vdt4GFu--gCESUaF_GidqF2plz8gyEd9poiK9yFpK4UGm49qjy9Jmq4kq8hpAqSudyFWAVQ9zWzWGElCLGm699pfzrAxx1m9-cybzUgy4nBByXyKl0LxS9AwIggyFU8-445k1cwNwSw-wEx2cg7G2MEaEy3C4UdqU41wvUy9x2h0Rwmo2Twm8fm0Oo3Vw5yw3e8dSewiV80-e0AmawWxS08Jw1pqm10gy798kz4t0Ag0F-0a6pCt09K0Oo0l7w2BEK0BU3fo0zqUzwpUuS3208Yw3do20wRg2txUu1Zw3p81k980IkAE0xgFUKwQ0ekjJoK0baw3wyw0hcocU1Y80lZg0vPw8lw15C06NE8EnG8c0GRx20KU6S0Eo2Uw4gxi1syUJ0c-10y89E50E7m31w_whpU3jwda0Noe8W0TE326oJoAu0Bj04Fg8i01JMw1uUW1Hym1twsU2rg6s70sxOfwd10ee0iW6pawlpFUK4Q7Edo4mbgvBx94mEpwyCXYE8ocUnK3O0XHglU9UW1SwDwBw4Dwh8-miq7o4O1ywwDgmwheK5ebxq1SwZzS1eEUGdCS9yqwNg8oaVE462Je09ToCbgWbx2q58F0wwci0C84EgibgW9g2ewpywb-0vO4oG362-0jV0dabyUG1py-yK7U5mbyQeyUlwaow3gy-1jCzA0A8nx64U4ii4U8EcocUlz86S0W808LoAwug08EU0Uh03o81FU2nBCwi2wkUcU0Nm6ELbg6V0c90oU9o2HxDw8-1KwfB2U4xw3Tp82Mg0Jd03J80AG0a_A81Og4Wex2i08mw4Lw",
        "__hsdp": "gczY58b2q1g53O4QlQCz924QCxqy23AeoAZIFd5ACgl7F19zszsmwC88hicwiCxN7gOvonCE4o8k1Thmu0Bx4MQjgjwqE2twdK0LChzywk9a70hQ2I6UhwBwp82kzUkxC0vm1ewbq19wa60lG08yzE5G5E0IK3i0he1Gwmod83Lw6SxK0tqm1ywlU1cE1q82Tw4jws8f80GS0WUiAg2LxG11xe7onwfa09cw2V8cE",
        "__hblp": "0ea3JwrES5EbUiyoGcws8kwjUb85G6E20wm86K0Do3rwc2m2O0gC2m1Aw9i2i6oeE2vwm82swwzo4i0g2aw9qU1lE2XwhE22wuUbUbEaUmw7Nwd28w58wGm3O3q1nwZwdO0kG2CehErxC0gO1bwiovwtU4a14w9-dxWm6E1q80zO6k5EG585-1hK0ii0Lo3mxi4F8qwnEdE6Cq1mw963-0YEfGho8oS1FxOdxm3m2C2S0hWlm0DVU2WCwHw",
        "__sjsp": "gczYeEi2QCwk1micBt9EOgyh0_oCdaiFp9A5hWgizYztEO2owx58O0jo3Ghm0FP3hd1e",
        "__comet_req": "15",
        "lsd": "AdSDcZVb_kw8axuZk0JzJHl4wAk",
        "jazoest": "22438",
        "__spin_r": "1043435019",
        "__spin_b": "trunk",
        "__spin_t": "1784442163",
        "__crn": "comet.fbweb.CometProfileReelsTabTabRoute",
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": "ProfileCometAppCollectionReelsRendererPaginationQuery",
        "server_timestamps": True,
        "variables": variables,
        "doc_id": "27781898651406539"
    }
    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://www.facebook.com',
        'priority': 'u=1, i',
        'referer': 'https://www.facebook.com/HungVlogOfficial/reels/',
        'sec-ch-prefers-color-scheme': 'light',
        'sec-ch-ua': '"Not;A=Brand";v="8", "Chromium";v="150", "Microsoft Edge";v="150"',
        'sec-ch-ua-full-version-list': '"Not;A=Brand";v="8.0.0.0", "Chromium";v="150.0.7871.115", "Microsoft Edge";v="150.0.4078.65"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-model': '""',
        'sec-ch-ua-platform': '"Windows"',
        'sec-ch-ua-platform-version': '"10.0.0"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0',
        'x-asbd-id': '359341',
        'x-fb-friendly-name': 'ProfileCometAppCollectionReelsRendererPaginationQuery',
        'x-fb-lsd': 'AdSDcZVb_kw8axuZk0JzJHl4wAk',
        'Cookie': 'datr=M21caiohl8GXrQtHeKqsz8xs; sb=M21cakGEXPH-rOSfHTQte9Ti; wd=1162x922; fr=1zAFgKbq8NwYRjKJ5.AWcRutA3EkDtZvz1J4V0hkF8gH5c3d-4Ao1jN4vx_XGTUW4OpUc.BqWD1W..AAA.0.0.BqWD1W.AWfzut87we3d2X857fsHBDdsuVk'
    }
    response = requests.request("POST", url, headers=headers, data=payload, timeout=timeout)
    response.raise_for_status()
    return response.text


# ---------------------------------------------------------------------------
# Parse view count "219K" / "1.4M" -> int
# ---------------------------------------------------------------------------
def parse_views(text: str) -> int:
    if not text:
        return 0
    t = text.strip().upper().replace(",", "")
    m = re.match(r"([\d.]+)\s*([KMB]?)", t)
    if not m:
        digits = re.sub(r"[^\d]", "", t)
        return int(digits) if digits else 0
    num = float(m.group(1))
    mult = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[m.group(2)]
    return int(num * mult)


# ---------------------------------------------------------------------------
# Parse response JSON
# ---------------------------------------------------------------------------
def _first_json(text: str) -> dict:
    """FB đôi khi trả nhiều object JSON nối nhau; lấy object đầu hợp lệ."""
    text = text.strip()
    if text.startswith("for (;;);"):
        text = text[len("for (;;);"):]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    depth = 0
    for i, ch in enumerate(text):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[: i + 1])
    raise ValueError("Không parse được JSON từ response.")


def _pick_thumbnail(sfvc: dict, node: dict) -> str:
    video = sfvc.get("video") or {}
    if video.get("first_frame_thumbnail"):
        return video["first_frame_thumbnail"]
    pv = sfvc.get("playback_video") or {}
    thumb = (pv.get("thumbnailImage") or {}).get("uri")
    if thumb:
        return thumb
    for att in node.get("attachments") or []:
        media = att.get("media") or {}
        if media.get("first_frame_thumbnail"):
            return media["first_frame_thumbnail"]
    return ""


def parse_reels_response(data: dict, page_id: str = "", limit: int = 10) -> PageResult:
    result = PageResult(page_id=page_id)
    try:
        node = data["data"]["node"]
    except (KeyError, TypeError):
        result.ok = False
        errs = (data or {}).get("errors")
        result.error = (
            errs[0].get("message", "Lỗi không rõ") if errs
            else "Response không có data.node (ID sai / hết hạn token?)."
        )
        return result

    edges = ((node or {}).get("aggregated_fb_shorts") or {}).get("edges") or []
    for edge in edges[:limit]:
        rnode = (edge.get("profile_reel_node") or {}).get("node") or {}
        sfvc = rnode.get("short_form_video_context") or {}
        video = sfvc.get("video") or {}
        message = rnode.get("message") or {}
        views_text = sfvc.get("play_count_reduced") or ""

        url = (
            sfvc.get("shareable_url")
            or (video.get("permalink_url") or "")
            or (f"https://www.facebook.com/reel/{video.get('id')}" if video.get("id") else "")
        )
        if not result.author:
            for actor in rnode.get("actors") or []:
                if actor.get("name"):
                    result.author = actor["name"]
                    break

        result.reels.append(
            Reel(
                video_id=video.get("id") or rnode.get("post_id") or "",
                description=message.get("text") or "",
                views_text=views_text,
                views_num=parse_views(views_text),
                thumbnail=_pick_thumbnail(sfvc, rnode),
                url=url,
                created=rnode.get("creation_time") or 0,
                duration_s=video.get("length_in_second") or 0.0,
            )
        )

    if not result.reels:
        result.ok = False
        result.error = result.error or "Không tìm thấy reel nào (Page không có reel?)."
    return result


# ---------------------------------------------------------------------------
# Quét 1 Page (nối 2 bước)
# ---------------------------------------------------------------------------
def scan_page(page_id: str, limit: int = 10, timeout: int = 30) -> PageResult:
    page_id = page_id.strip()
    try:
        pfbid = get_pfbid(page_id, timeout=timeout)
    except requests.RequestException as e:
        return PageResult(page_id=page_id, ok=False, error=f"Lỗi mạng (lấy node id): {e}")
    except ValueError as e:
        return PageResult(page_id=page_id, ok=False, error=str(e))

    try:
        text = get_view(pfbid, timeout=timeout)
        data = _first_json(text)
    except requests.RequestException as e:
        return PageResult(page_id=page_id, ok=False, node_id=pfbid, error=f"Lỗi mạng: {e}")
    except ValueError as e:
        return PageResult(page_id=page_id, ok=False, node_id=pfbid, error=str(e))

    res = parse_reels_response(data, page_id=page_id, limit=limit)
    res.node_id = pfbid
    return res
