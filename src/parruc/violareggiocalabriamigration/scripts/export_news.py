# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import argparse
import copy
import json
import logging
import os
import shutil
import sys

import requests

from bs4 import BeautifulSoup
from plone.i18n.normalizer import idnormalizer

logger = logging.getLogger("unibo.fondazionezerimigrator.export")
logging.basicConfig(level=logging.WARNING)

usage = "usage: %prog [options]"
parser = argparse.ArgumentParser(usage=usage, description=__doc__)
parser.add_argument(
    "-p", "--path", type=str, dest="export_path", default="exported",
    help="Results export folder. Default is 'exported'")
parser.add_argument(
    "-l", "--limit", type=int, dest="limit", default=0,
    help="Limit the number of pages to import (for debugging purpose)")
parser.add_argument(
    "-o", "--offset", type=int, dest="offset", default=0,
    help="Skips a certain number of pages (for debugging purpose)")
parser.add_argument(
    "-f", "--force",
    action="store_true", dest="force", default=False,
    help="Dont trust current structure, and overwrite it (slower)")


reject_links = ["#"]

VISITED_PAGES = []
TAKEN_PATHS = []
REDIRECTS = {}
BASE_URL = "http://www.fondazionezeri.unibo.it"
COUNTER = 0
normalize = idnormalizer.normalize


def get_absolute_link(link):
    if link == "#":
        return ""
    if link.startswith("/"):
        link = BASE_URL + link
    if link.startswith("www.fondazionezeri.unibo.it"):
        link = link.replace("www.fondazionezeri.unibo.it", BASE_URL)
    return link


def parse_menu(parser):
    menu = []
    sections = parser.find_all('div', {'class': ['divprinc', ]})
    for section in sections:
        section_container = section.find("div", {'class': ['divsec', ]})
        if not section_container:
            continue
        section_links = section_container.find_all('a')
        menu_item = {
            "title": section.find("a").string,
            "children": [],
        }
        for section_link in section_links:
            link = get_absolute_link(section_link.get("href", ""))
            if not link:
                continue
            sub_menu_item = {
                'url': link,
                'title': section_link.string,
            }
            menu_item["children"].append(sub_menu_item)
        menu.append(menu_item)
    return menu


def find_first_available_path(path):
    count = 0
    new_path = path
    while new_path in TAKEN_PATHS:
        new_path = path + "_" + str(count).zfill(2)
        count += 1
    TAKEN_PATHS.append(new_path)
    return new_path


def scrape_subpages(export_path, source_data):
    if "parser" in source_data:
        parser = source_data.pop("parser")
    else:
        parser = BeautifulSoup(source_data["it"]["content"], 'html.parser')
    logger.info("scraping subpage %s", source_data['it']['path'])
    content = parser.find("table", {"class": "centro"})
    if not content:
        return
    for link in content.find_all(["a", "img"]):
        href = ""
        if "href" in link.attrs:
            href = get_absolute_link(link.get("href"))
        elif "src" in link.attrs:
            href = get_absolute_link(link.get("src"))
        if not href or not href.startswith(BASE_URL):
            continue
        if href.endswith((".pdf", ".gif", ".png", ".jpg", ".jpeg",
                          ".doc", ".docx")):
            data = prepare_dict(href, is_file=True)
        else:
            data = prepare_dict(href)
            if data and data["type"] == "content":
                scrape_subpages(export_path, data)
        if data:
            save_json(export_path, data)


def save_json(export_path, data):
    global COUNTER
    if not data:
        return
    data["count"] = COUNTER
    if "parser" in data:
        data.pop("parser")
    file_name = data["it"]["path"]
    file_name = file_name.lstrip("/").replace("/", "-").replace("%20", "-")
    file_name += ".json"
    path = os.sep.join((export_path, file_name))
    if file_name.startswith("amici-di-federico-zeri"):
        return
    with open(path, 'w') as f:
        json.dump(data, f)
    COUNTER += 1


def get_url_checking(url):
    if not url:
        logger.warning("Found an empty link to '%s'", url)
        return None
    if url in VISITED_PAGES:
        logger.info("Link '%s' already visited", url)
        return None
    req = requests.get(url)
    try:
        req.raise_for_status()
    except:
        logger.warning("Found a broken link to '%s'", url)
        return None
    if req.url in VISITED_PAGES:
        logger.warning("Link redirected to already visited page '%s'", req.url)
        return None
    if not req.url.startswith(BASE_URL):
        logger.info("Link '%s' points outside", req.url)
        return None
    VISITED_PAGES.append(req.url)
    return req


def clean_html(source_content, lang):
    content = copy.copy(source_content)
    if not content:
        return ""
    for tag in content.findAll(True):
        for item in tag.attrs.keys():
            if item in ("onclick", "align", "id", "style"):
                del(tag[item])
            if tag.name == "img" and item == "name":
                del(tag[item])
            if tag.name in ("a", "img") and item in ("href", "src"):

                url = get_absolute_link(tag[item])
                if not url.startswith(BASE_URL):
                    continue
                req = requests.get(url)
                url = req.url
                if url.startswith(BASE_URL):
                    url = url.replace(BASE_URL, "")
                    if tag.name == "a":
                        if "target" in tag.attrs.keys():
                            del(tag["target"])
                        if not url.endswith((".pdf", ".doc", ".docx")):
                            tag[item] = url
                            continue
                else:
                    tag[item] = url
                    continue
                query_string = ""
                if "?" in url:
                    url, query_string = url.rsplit("?", 1)
                file_name_type = url.split("/")[-1].replace("%20", " ")
                filename, filetype = file_name_type.rsplit(".", 1)
                filename = normalize(filename)
                levels = url.split("/")
                norm_levels = [normalize(l.strip()) for l in levels[:-1]]
                norm_levels.append(filename)
                for n, level in enumerate(norm_levels):
                    if level == "home":
                        norm_levels[n] = "it"
                    if level == "home-eng":
                        norm_levels[n] = "en"
                norm_levels = norm_levels[:-2] + ['_'.join(norm_levels[-2:])]
                path = "/".join(norm_levels)
                path = find_first_available_path(path) + "." + filetype
                tag[item] = path
                if query_string:
                    tag[item] = tag[item] + "?" + query_string
                if filetype in ("gif", "png", "jpg", "jpeg"):
                    tag[item] = tag[item].replace("/allegati/",
                                                  "/immagini/")
                    tag[item] = tag[item].replace("/images/",
                                                  "/immagini/")
                    tag[item] = tag[item].replace("/s2magazine/",
                                                  "/immagini/")
                if lang == "en":
                    tag[item] = tag[item].replace("/immagini/",
                                                  "/en/images/migration/")
                    tag[item] = tag[item].replace("/allegati/",
                                                  "/en/attachments/migration/")
                if lang == "it":
                    tag[item] = tag[item].replace("/immagini/",
                                                  "/it/immagini/migrazione/")
                    tag[item] = tag[item].replace("/allegati/",
                                                  "/it/allegati/migrazione/")
    return content.encode('utf-8')


def prepare_dict(url, is_file=False):
    req = get_url_checking(url)
    data = {}
    if not req:
        return None
    if is_file:
        file_name_type = url.split("/")[-1].replace("%20", " ")
        filename, filetype = file_name_type.rsplit(".", 1)
        filename = normalize(filename)
        levels = url.replace(BASE_URL, "").split("/")
        norm_levels = [normalize(l.strip()) for l in levels[:-1]]
        norm_levels.append(filename)
        if "fondazionezeri" in norm_levels:
            norm_levels.remove("fondazionezeri")
        data["type"] = "file"
        data["url"] = url
        data["filename"] = filename + "." + filetype
        norm_levels = norm_levels[:-2] + ['_'.join(norm_levels[-2:])]
        path = "/".join(norm_levels)
        path = find_first_available_path(path) + "." + filetype
        if filetype in ("gif", "png", "jpg", "jpeg"):
            data["ct"] = "Image"
            path = path.replace("/allegati/", "/immagini/")
            path = path.replace("/images/", "/immagini/")
            path = path.replace("/s2magazine/", "/immagini/")
        else:
            data["ct"] = "File"
        it_path = path.replace("/immagini/", "/it/immagini/migrazione/")
        it_path = it_path.replace("/allegati/", "/it/allegati/migrazione/")
        data["it"] = {"path": it_path}
        en_path = path.replace("/immagini/", "/en/images/migration/")
        en_path = en_path.replace("/allegati/", "/en/attachments/migration/")
        data["en"] = {"path": en_path}
        return data
    text = unicode(req.content.decode('ISO-8859-1')).replace(u"\u0092", u"'")
    parser = BeautifulSoup(text, 'html.parser')
    data["parser"] = parser
    content = clean_html(parser.find("div", {"class": "testo"}), "it")
    description = ""
    preocchiello = parser.find("div", {"class": "preocchiello"})
    sottotitolo = parser.find("div", {"class": "sottotitolo"})
    if preocchiello:
        description += preocchiello.text
    if sottotitolo:
        description += sottotitolo.text
    title = parser.find("div", {"class": "titolo"}).text
    element_type = "content"
    ct = "contenutoordinario"
    if len(parser.find_all("div", {"class": "elenco"})) > 0:
        ct = "automaticsummary"
    data["ct"] = ct
    data["type"] = element_type
    breadcrumbs = parser.find("div", {"class": "bread"})
    levels = breadcrumbs.text.split(u"\xbb")
    normalized_levels = [normalize(l.strip()) for l in levels]
    if "home" in normalized_levels:
        normalized_levels[normalized_levels.index("home")] = "it"
    child_path = "/" + "/".join(normalized_levels)
    child_path = find_first_available_path(child_path)
    data["it"] = {"id": normalized_levels[-1], "path": child_path,
                  "title": title, "content": content,
                  "description": description, "url": req.url, }
    en_link = parser.find("a", {"id": "ling2"})
    if not en_link:
        logger.warning("Missing EN link for %s", url)
        return data
    en_url = get_absolute_link(en_link.get("href"))
    if not en_url:
        logger.warning("Empty EN link for %s", url)
        return data
    en_req = get_url_checking(en_url)
    if not en_req:
        logger.warning("Empty en req for %s", url)
        return data
    en_text = unicode(en_req.content.decode('ISO-8859-1')).replace(u"\u0092",
                                                                   u"'")
    en_parser = BeautifulSoup(en_text, 'html.parser')
    en_content = clean_html(en_parser.find("div", {"class": "testo"}), "en")
    en_description = ""
    en_preocchiello = en_parser.find("div", {"class": "preocchiello"})
    en_sottotitolo = en_parser.find("div", {"class": "sottotitolo"})
    if en_preocchiello:
        en_description += en_preocchiello.text
    if en_sottotitolo:
        en_description += en_sottotitolo.text
    if (u"Avviso: la pagina non \xe8 disponibile") in en_parser.text:
        logger.warning("Missing translation for %s", url)
        return data
    en_title = en_parser.find("div", {"class": "titolo"}).text
    en_breadcrumbs = en_parser.find("div", {"class": "bread"})
    en_levels = en_breadcrumbs.text.split(u"\xbb")
    en_normalized_levels = [normalize(l.strip()) for l in en_levels]
    if "home-eng" in en_normalized_levels:
        en_normalized_levels[en_normalized_levels.index("home-eng")] = "en"
    en_child_path = "/" + "/".join(en_normalized_levels)
    en_child_path = find_first_available_path(en_child_path)
    data["en"] = {"id": en_normalized_levels[-1], "path": en_child_path,
                  "title": en_title, "content": en_content,
                  "description": en_description, "url": en_req.url, }
    return data


def export(offset, limit, force, export_path):
    req = get_url_checking(BASE_URL)
    parser = BeautifulSoup(req.text, 'html.parser')
    menu_it = parse_menu(parser)
    req = get_url_checking(BASE_URL + "/home_eng/00000208_Home_Eng.html")
    parser_en = BeautifulSoup(req.text, 'html.parser')
    menu_en = parse_menu(parser_en)
    if not os.path.exists(export_path):
            os.makedirs(export_path)
    data = {"type": "first_level", 'ct': "Folder"}
    data["it"] = {"id": "it", "path": "/it",
                  "title": "it"}
    data["en"] = {"id": "en", "path": "/en",
                  "title": "en"}
    save_json(export_path, data)
    for first_level_it, first_level_en in zip(menu_it, menu_en):
        data = {"type": "first_level", 'ct': "Folder", }
        id_it = normalize(first_level_it["title"])
        id_en = normalize(first_level_en["title"])
        first_path_it = "/it/" + id_it
        first_path_en = "/en/" + id_en
        data["it"] = {"id": id_it, "path": first_path_it,
                      "title": first_level_it["title"]}
        data["en"] = {"id": id_en, "path": first_path_en,
                      "title": first_level_en["title"]}
        save_json(export_path, data)
        for second_level in first_level_it["children"]:
            data = prepare_dict(second_level['url'])
            if data and data["type"] == "content":
                scrape_subpages(export_path, data)
            save_json(export_path, data)


def main(*args, **kwargs):
    # Older plone versions dont add automatic -c script parameters
    # So I'll stripe the parameters until I reach the script
    if "-c" in sys.argv:
        cmd_args = sys.argv[3:]
    else:
        cmd_args = sys.argv[1:]
    options = vars(parser.parse_args(cmd_args))
    original_path = options["export_path"]
    if "force" in options and options["force"]:
        shutil.rmtree(original_path)
    export(**options)
