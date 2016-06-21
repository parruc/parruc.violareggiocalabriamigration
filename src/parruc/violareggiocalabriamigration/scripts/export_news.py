# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import re
import argparse
import json
import logging
import os
import shutil
import sys

import requests

from bs4 import BeautifulSoup
from datetime import date
from plone.i18n.normalizer import idnormalizer

logger = logging.getLogger("unibo.violareggiocalabriamigration.export")
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
BASE_URL = "http://www.violareggiocalabria.it"
COUNTER = 0
MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
          "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
months = "|".join(MONTHS)
date_re = re.compile(".*?([0-9]{1,2})\s*(" + months + ")\s*([0-9]{4}).*")
normalize = idnormalizer.normalize


def get_absolute_link(link):
    if link == "#":
        return ""
    if link.startswith("/"):
        link = BASE_URL + link
    if link.startswith("www.violareggiocalabria.it"):
        link = link.replace("www.violareggiocalabria.it", BASE_URL)
    return link


def save_json(export_path, data):
    global COUNTER
    if not data:
        return
    data["count"] = COUNTER
    file_name = normalize(data["title"].strip()) + ".json"
    path = os.sep.join((export_path, file_name))
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


def prepare_dict(url):
    req = get_url_checking(url)
    if not req:
        return
    parser = BeautifulSoup(req.content, 'html.parser')
    article = parser.select("div.item-page")[0]
    title = article.select("h2.art-postheader")[0].text
    img = parser.find("img")
    if len(img) > 0:
        img = img[0]
    img_src = ""
    img_alt = ""
    if img and "src" in img.attrs:
        img_src = get_absolute_link(img.get("src"))
    if img and "alt" in img.attrs:
        img_alt = img.get("alt")
    text = ""
    for paragraph in article.findAll("p")[:-1]:
        paragraph_text = paragraph.get_text().strip()
        if paragraph_text:
            text += "<p>" + paragraph_text + "</p>"
    last_p = article.findAll("p")[-1].get_text()
    date_match = date_re.match(last_p.lower())
    mydate = ""
    if date_match:
        day = int(date_match.group(1))
        month = date_match.group(2)
        year = int(date_match.group(3))
        month = MONTHS.index(month) + 1
        mydate = date(year, month, day)
    else:
        logger.warning("%s not a date" % last_p)
        text += "<p>" + last_p + "</p>"
    return {"id":normalize(title), "title": title, "img_src": img_src,
            "img_alt": img_alt, "text": text, "url": req.url, "date": mydate}


def export_news(offset, limit, force, export_path):
    out = []
    req = get_url_checking("http://www.violareggiocalabria.it/sitemap.xml")
    parser = BeautifulSoup(req.content, 'xml')
    url_tags = parser.findAll('url')
    if not os.path.exists(export_path):
        os.makedirs(export_path)
    for url_tag in url_tags:
        url = url_tag.find('loc').string
        if "catid=7:news" in url and "Itemid=" in url:
            res = prepare_dict(url)
            if res:
                save_json(export_path, res)


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
    export_news(**options)
