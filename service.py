# -*- coding: utf-8 -*-
# Service LegendasDivx.com version 1.0.8
# Code based on Undertext (FRODO) service
# Coded by HiGhLaNdR@OLDSCHOOL
# Ported to Gotham by HiGhLaNdR@OLDSCHOOL
# Help by VaRaTRoN
# Bugs & Features to highlander@teknorage.com
# http://www.teknorage.com
# License: GPL v2

import os
from os.path import join as pjoin
import fnmatch
import shutil
import sys
import string
import time
import unicodedata
import urllib.request, urllib.parse, urllib.error
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
import http.cookiejar
import uuid
import socket
from urllib.parse import unquote, quote_plus
import urllib.error
import re
import html


_addon = xbmcaddon.Addon()
_author     = _addon.getAddonInfo('author')
_scriptid   = _addon.getAddonInfo('id')
_scriptname = _addon.getAddonInfo('name')
_version    = _addon.getAddonInfo('version')
_language   = _addon.getLocalizedString
_dialog     = xbmcgui.Dialog()

_cwd        = xbmcvfs.translatePath(_addon.getAddonInfo('path'))
_profile    = xbmcvfs.translatePath(_addon.getAddonInfo('profile'))
_resource   = xbmcvfs.translatePath(os.path.join(_cwd, 'resources', 'lib' ))
_temp       = xbmcvfs.translatePath(os.path.join(_profile, 'temp'))

if os.path.isdir(_temp):shutil.rmtree(_temp)
xbmcvfs.mkdirs(_temp)
if not os.path.isdir(_temp):xbmcvfs.mkdir(_temp)

sys.path.append (_resource)

_descon = _addon.getSetting( 'DESC' )
_search = _addon.getSetting( 'SEARCH' )
debug = _addon.getSetting( 'DEBUG' )

main_url = "https://www.legendasdivx.pt/"
debug_pretext = "LegendasDivx"

INTERNAL_LINK_URL = "plugin://%(scriptid)s/?action=download&id=%(id)s&filename=%(filename)s"
SUB_EXTS = ['srt', 'sub', 'txt', 'ass', 'ssa', 'smi']
HTTP_USER_AGENT = "User-Agent=Kodi 19 Matrix"

#====================================================================================================================
# Regular expression patterns
#====================================================================================================================

subtitle_pattern = r"<div\sclass=\"sub_box\">.+?<div\sclass=\"sub_header\">.+?<b>(.+?)</b>\s\((\d\d\d\d)\)\s.+?name=User_Info&username=(.+?)'><b>.+?</div>.+?<table\sclass=\"sub_main\scolor1\"\scellspacing=\"0\">.+?<tr>.+?<th>CDs:</th>.+?<td>(.+?)</td>.+?<a\shref=\"\?name=Downloads&d_op=ratedownload&lid=(.+?)\">.+?<th\sclass=\"color2\">Hits:</th>.+?<td>([^\s]+).+?<td>(.+?)</td>.+?<td\scolspan=\"5\"\sclass=\"td_desc\sbrd_up\">(.*?)</td>.+?<td\sclass"
release_pattern = r"([^\W][\w\.]{1,}\w{1,}[\.]{1,1}[^\.|^\ |^\.org|^\.com|^\.net][^\Ws|^\.org|^\.com|^\.net][\w{1,}\.|\-|\(\d\d\d\d\)|\[\d\d\d\d\]]{3,}[^\Ws|^\.org|^\.com|^\.net][\w{3,}\-|\.{1,1}]\w{2,})"
release_pattern1 = r"([^\W][\w\ |\]|[]{4,}[^\Ws][x264|xvid|ac3]{1,}-[\w\[\]]{1,})"
year_pattern = r"(19|20)\d{2}$"

#==========
# Functions
#==========

def _log(module, msg):
    s = "### [%s] - %s" % (module, msg)
    xbmc.log(s, level=xbmc.LOGDEBUG)

def log(msg):
    if debug == 'true': _log(_scriptname, msg)

def recursive_glob(treeroot, extensions):
    extensions = set(extensions)
    results = []
    for base, dirs, files in os.walk(treeroot):
        for filename in files:
            _, ext = os.path.splitext(filename)
            if ext.lower() in extensions:
                results.append(os.path.join(base, filename))
    return results

def xbmc_extract(SRC, DEST):
    dd_ext, ff_ext = xbmcvfs.listdir(SRC)
    ff_ext = (ff for ff in ff_ext if os.path.splitext(ff)[1][1:].lower() in SUB_EXTS)
    dest_path = xbmcvfs.translatePath(DEST)
    for ff in ff_ext:
        src_file = os.path.join(SRC, ff)
        dst_file = os.path.join(dest_path, ff)
        success = xbmcvfs.copy(src_file,dst_file)
        if not success:
            log("Error extracting: '%s' to '%s'" % (src_file,dst_file))
        else:
            log("Extracting: '%s' to '%s'" % (src_file,dst_file))
    for dd in dd_ext:
        dd_mk = os.path.join(DEST, dd)
        os.makedirs(dd_mk, exist_ok=True)
        now_SRC = os.path.join(SRC, dd, '')
        now_DEST = os.path.join(DEST, dd)
        success_dd = xbmc_extract(now_SRC, now_DEST)
        if not success_dd:
            log("Error extracting inside dir: '%s' to '%s'" % (now_SRC,now_DEST))
        else:
            log("Extracting (back into the ff loop: '%s' to '%s'" % (now_SRC,now_DEST))

def fix_encoding(text):
    if not text:
        return ""
    text = html.unescape(text)
    try:
        text = text.encode('latin1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return text

def clean_script_tags(text):
    if not text:
        return ""
    # Strip <script>...</script> content entirely
    return re.sub(r'<script.*?>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)

def login():
    username = _addon.getSetting( 'LDuser' )
    password = _addon.getSetting( 'LDpass' )
    login_postdata = urllib.parse.urlencode({'username' : username, 'password' : password, 'login' : 'Login', 'sid' : ''}).encode("utf-8")
    cj = http.cookiejar.CookieJar()
    my_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    urllib.request.install_opener(my_opener)
    request = urllib.request.Request(main_url + 'forum/ucp.php?mode=login', login_postdata)
    raw_response = urllib.request.urlopen(request, None, 6.5).read()
    try:
        response = raw_response.decode('utf-8')
    except UnicodeDecodeError:
        response = raw_response.decode('ISO-8859-1', errors='replace')
    return my_opener

def urlpost(query, lang, page):
    my_opener = login()
    postdata = urllib.parse.urlencode({'query': query, 'form_cat': lang}).encode("utf-8")
    headers = {'Referer': main_url + 'modules.php?name=Downloads&file=jz&d_op=search&op=_jz00&page=' + str(page)}
    request = urllib.request.Request(main_url + 'modules.php?name=Downloads&file=jz&d_op=search&op=_jz00&page=' + str(page), data=postdata, headers=headers)
    log("POST url page: %s" % page)
    log("POST url data: %s" % postdata)
    try:
        raw_response = urllib.request.urlopen(request, None, 6.5).read()
        try:
            response = raw_response.decode('utf-8')
        except UnicodeDecodeError:
            response = raw_response.decode('ISO-8859-1', errors='replace')
    except urllib.error.URLError as e:
        response = ''
        _dialog.notification(_scriptname, _language(32025).encode('utf8'), xbmcgui.NOTIFICATION_ERROR)
        log("Oops, site down?")
    except socket.timeout:
        response = ''
        _dialog.notification(_scriptname, _language(32026).encode('utf8'), xbmcgui.NOTIFICATION_ERROR)
        log("Timed out!")
    return response
        
def getallsubs(searchstring, languageshort, languagelong, file_original_path, searchstring_notclean):
    subtitles_list = []

    log("getallsubs: Search String = '%s'" % searchstring)
    log("getallsubs: Search String Not Clean = '%s'" % searchstring_notclean)
    page = 1
    listsResult = 0
    if languageshort == "pt": content = urlpost(searchstring, "28", page)
    elif languageshort == "pb": content = urlpost(searchstring, "29", page)
    elif languageshort == "es": content = urlpost(searchstring, "30", page)
    elif languageshort == "en": content = urlpost(searchstring, "31", page)
    log("getallsubs: LanguageShort = '%s'" % languageshort) 

    while content and re.search(subtitle_pattern, content, re.IGNORECASE | re.DOTALL | re.MULTILINE) and page < 6:
        for matches in re.finditer(subtitle_pattern, content, re.IGNORECASE | re.DOTALL | re.X):
            uploader = matches.group(3)
            hits = matches.group(6)
            id = matches.group(5)
            id = str.split(id, '"')
            id = id[0]
            movieyear = matches.group(2)
            no_files = matches.group(4)
            downloads = int(matches.group(6)) / 200
            if (downloads > 5): downloads=5
            filename = str.strip(matches.group(1))
            desc_ori = str.strip(matches.group(8))

            # Strip inline scripts before parsing text
            filename = clean_script_tags(filename)
            desc_ori = clean_script_tags(desc_ori)
            uploader = clean_script_tags(uploader)

            desc_ori = re.sub('www.legendasdivx.com','',desc_ori)
            log("getallsubs: Original Decription = '%s'" % desc_ori)
            
            # Remove new lines on the commentaries
            filename = re.sub('\n',' ',filename)
            _filenameon = "true"
            if _descon == "false":
                desc = re.findall(release_pattern, desc_ori, re.IGNORECASE | re.VERBOSE | re.DOTALL | re.UNICODE | re.MULTILINE)
                desc = " / ".join(desc)
                if desc != "": _filenameon = "false"
                if desc == "":
                    desc = re.findall(release_pattern1, desc_ori, re.IGNORECASE | re.VERBOSE | re.DOTALL | re.UNICODE | re.MULTILINE)
                    desc = " / ".join(desc)
                    if desc != "": _filenameon = "false"
                    if desc == "": desc = desc_ori; _filenameon = "true"
                    else: desc = desc; _filenameon = "false"
            else: desc = desc_ori; _filenameon = "true"
            desc = re.sub('<br />',' ',desc)
            desc = re.sub('<br>',' ',desc)
            desc = re.sub('\n',' ',desc)
            desc = re.sub(':.','',desc)

            # Remove HTML tags and remaining script residue
            filename = re.sub('\n',' ',filename)
            desc = re.sub(r'<[^<]+?>|[~]','', desc)

            # Apply encoding and HTML entity cleanup
            filename = fix_encoding(filename)
            desc = fix_encoding(desc)
            uploader = fix_encoding(uploader)

            log("getallsubs: Final Description = '%s'" % desc)

            filesearch = os.path.abspath(file_original_path)
            log("getallsubs: Filesearch String = '%s'" % filesearch)
            filesearch = os.path.split(filesearch)
            dirsearch = filesearch[0].split(os.sep)
            log("getallsubs: dirsearch = '%s'" % dirsearch)
            dirsearch_check = str.split(dirsearch[-1], '.')
            log("getallsubs: dirsearch_check = '%s'" % dirsearch_check)

            _parentfolder = _addon.getSetting( 'PARENT' )
            if _parentfolder == '0':
                if re.search(release_pattern, dirsearch[-1], re.IGNORECASE): _parentfolder = '1'
                else: _parentfolder = '2'
            if _parentfolder == '1':
                if re.search(dirsearch[-1], desc, re.IGNORECASE): sync = True
                else: sync = False
            if _parentfolder == '2':
                if (searchstring_notclean != ""):
                    sync = False
                    if str.lower(searchstring_notclean) in str.lower(desc): sync = True
                else:
                    if (str.lower(dirsearch_check[-1]) == "rar") or (str.lower(dirsearch_check[-1]) == "cd1") or (str.lower(dirsearch_check[-1]) == "cd2"):
                        sync = False
                        if len(dirsearch) > 1 and dirsearch[1] != '':
                            if re.search(filesearch[1][:len(filesearch[1])-4], desc, re.IGNORECASE) or re.search(dirsearch[-2], desc, re.IGNORECASE): sync = True
                        else:
                            if re.search(filesearch[1][:len(filesearch[1])-4], desc, re.IGNORECASE): sync = True
                    else:
                        sync = False
                        if len(dirsearch) > 1 and dirsearch[1] != '':
                            if re.search(filesearch[1][:len(filesearch[1])-4], desc) or re.search(dirsearch[-1], desc, re.IGNORECASE): sync = True
                        else:
                            if re.search(filesearch[1][:len(filesearch[1])-4], desc, re.IGNORECASE): sync = True

            if _filenameon == "false": filename = "From: " + uploader + " - "  + desc + "  " + "hits: " + hits
            else: filename = "From: " + uploader + " - "  + filename + " " + "(" + movieyear + ")" + "  " + "hits: " + hits + " - " + desc
            
            subtitles_list.append({'rating': str(downloads), 'filename': filename, 'uploader': uploader, 'desc': desc, 'sync': sync, 'hits' : hits, 'id': id, 'language_short': languageshort, 'language_name': languagelong})
            log("getallsubs: SUBS LIST = '%s'" % subtitles_list)
            listsResult = listsResult + 1 
        
        page = page + 1
        if listsResult == 5 and page < 6:
            if languageshort == "pt": content = urlpost(searchstring, "28", page)
            elif languageshort == "pb": content = urlpost(searchstring, "29", page)
            elif languageshort == "es": content = urlpost(searchstring, "30", page)
            elif languageshort == "en": content = urlpost(searchstring, "31", page)
            listsResult = 0
        else:
            page = 6
    
    # Bubble sort, to put syncs on top
    for n in range(0,len(subtitles_list)):
        for i in range(1, len(subtitles_list)):
            temp = subtitles_list[i]
            if subtitles_list[i]["sync"] > subtitles_list[i-1]["sync"]:
                subtitles_list[i] = subtitles_list[i-1]
                subtitles_list[i-1] = temp
                
    return subtitles_list

def append_subtitle(item):
    listitem = xbmcgui.ListItem(
                   label=item['language_name'],
                   label2=item['filename']
               )
    listitem.setArt( { "icon": str(int(round(float(item["rating"])))), "thumb" : item["language_short"] } )
    listitem.setProperty("sync", 'true' if item["sync"] else 'false')
    listitem.setProperty("hearing_imp", 'true' if item.get("hearing_imp", False) else 'false')

    args = dict(item)
    args['scriptid'] = _scriptid
    url = INTERNAL_LINK_URL % args
    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=listitem, isFolder=False)

class Main:

    def Search(item):
        """Called when searching for subtitles from KODI."""
        username = _addon.getSetting( 'LDuser' )
        password = _addon.getSetting( 'LDpass' )
        if not username or not password:
            xbmcplugin.endOfDirectory(int(sys.argv[1]))
            if username == '' and password != '': _dialog.notification(_scriptname, _language(32016).encode('utf8'), xbmcgui.NOTIFICATION_ERROR)
            if username != '' and password == '': _dialog.notification(_scriptname, _language(32017).encode('utf8'), xbmcgui.NOTIFICATION_ERROR)
            if username == '' and password == '': _dialog.notification(_scriptname, _language(32018).encode('utf8'), xbmcgui.NOTIFICATION_ERROR)
        file_original_path = item['file_original_path']
        _parentfolder = _addon.getSetting( 'PARENT' )
        if _parentfolder == '0':
            filename = os.path.abspath(file_original_path)
            dirsearch = filename.split(os.sep)
            log("getallsubs: dirsearch string _parentfolder is 0 = %s" % (dirsearch,))
            if re.search(release_pattern, dirsearch[-2], re.IGNORECASE): _parentfolder = '1'
            else: _parentfolder = '2'
        if _parentfolder == '1':
            filename = os.path.abspath(file_original_path)
            dirsearch = filename.split(os.sep)
            filename = dirsearch[-2]
            log("getallsubs: filename string _parentfolder is 1 = %s" % (filename,))
        if _parentfolder == '2':   
            filename = os.path.splitext(os.path.basename(file_original_path))[0]
            log("getallsubs: filename string _parentfolder is 2 = %s" % (filename,))
     
        filename = xbmc.getCleanMovieTitle(filename)[0] + " " + xbmc.getCleanMovieTitle(filename)[1]
        log("Search: FILENAME = %s" % (filename,))
        searchstring_notclean = os.path.splitext(os.path.basename(file_original_path))[0]
        searchstring = ""
        global israr
        israr = os.path.abspath(file_original_path)
        israr = os.path.split(israr)
        israr = israr[0].split(os.sep)
        israr = str.split(israr[-1], '.')
        israr = str.lower(israr[-1])

        title = xbmc.getCleanMovieTitle(item['title'])[0]
        year = item['year']
        tvshow = item['tvshow']
        tvshow = tvshow.split('(')
        tvshow = tvshow[0]
        season = item['season']
        episode = item['episode']
        log("Search: Tvshow string = %s" % (tvshow,))
        log("Search: Title string = %s" % (title,))
        subtitles_list = []
        
        if item['mansearch']:
            searchstring = '"' + item['mansearchstr'] + '"'
            log("Search: Manual String = %s" % (searchstring,))
        else:
            if episode != '':
                searchstring = "%s S%#02dE%#02d" % (title, int(season), int(episode))
                log("Search: Title TV LIBRARY String = %s" % (searchstring,))
            elif title != '' and episode == '':
                searchstring = '"' + title + ' ' + year + '"'
                log("Search: Title MOVIE LIBRARY String = %s" % (searchstring,))
            else:
                if 'rar' in israr and searchstring is not None:
                    log("Search: RAR Filename String = %s" % (searchstring,))
                    if 'cd1' in str.lower(title) or 'cd2' in str.lower(title) or 'cd3' in str.lower(title):
                        dirsearch = os.path.abspath(file_original_path)
                        dirsearch = os.path.split(dirsearch)
                        dirsearch = dirsearch[0].split(os.sep)
                        if len(dirsearch) > 1:
                            searchstring_notclean = dirsearch[-3]
                            searchstring = xbmc.getCleanMovieTitle(dirsearch[-3])
                            searchstring = searchstring[0]
                            log("Search: RAR MULTI CD String = %s" % (searchstring,))
                        else: searchstring = title
                    else:
                        searchstring = filename
                        log("Search: RAR NO MULTI CD String = %s" % (searchstring,))
                elif 'cd1' in str.lower(title) or 'cd2' in str.lower(title) or 'cd3' in str.lower(title):
                    dirsearch = os.path.abspath(file_original_path)
                    dirsearch = os.path.split(dirsearch)
                    dirsearch = dirsearch[0].split(os.sep)
                    if len(dirsearch) > 1:
                        searchstring_notclean = dirsearch[-2]
                        searchstring = xbmc.getCleanMovieTitle(dirsearch[-2])
                        searchstring = searchstring[0]
                        log("Search: MULTI CD String = %s" % (searchstring,))
                    else:
                        title = os.path.split(file_original_path)
                        searchstring = title[-1]
                else:
                    if _search == '0':
                        if re.search("(.+?s[0-9][0-9]e[0-9][0-9])", filename, re.IGNORECASE):
                            searchstring = re.search("(.+?s[0-9][0-9]e[0-9][0-9])", filename, re.IGNORECASE)
                            searchstring = searchstring.group(0)
                            log("Search: Filename is TV String (search is 0) = %s" % (searchstring,))
                        else:
                            searchstring = '"' + filename + '"'
                            log("Search: Filename is Not TV String (search is 0) = %s" % (searchstring,))
                    else:
                        if re.search("(.+?s[0-9][0-9]e[0-9][0-9])", title, re.IGNORECASE):
                            searchstring = re.search("(.+?s[0-9][0-9]e[0-9][0-9])", title, re.IGNORECASE)
                            searchstring = searchstring.group(0)
                            log("Search: Title is TV String (search is 1) = %s" % (searchstring,))
                        else:
                            searchstring = title
                            log("Search: Title is Not TV String (search is 1) = %s" % (searchstring,))

        PT_ON = _addon.getSetting( 'PT' )
        PTBR_ON = _addon.getSetting( 'PTBR' )
        ES_ON = _addon.getSetting( 'ES' )
        EN_ON = _addon.getSetting( 'EN' )
        
        if 'por' in item['languages'] and PT_ON == 'true':
            subtitles_list = getallsubs(searchstring, "pt", "Portuguese", file_original_path, searchstring_notclean)
            for sub in subtitles_list: append_subtitle(sub)
        if 'por' in item['languages'] and PTBR_ON == 'true':
            subtitles_list = getallsubs(searchstring, "pb", "Brazilian", file_original_path, searchstring_notclean)
            for sub in subtitles_list: append_subtitle(sub)
        if 'spa' in item['languages'] and ES_ON == 'true':
            subtitles_list = getallsubs(searchstring, "es", "Spanish", file_original_path, searchstring_notclean)
            for sub in subtitles_list: append_subtitle(sub)
        if 'eng' in item['languages'] and EN_ON == 'true':
            subtitles_list = getallsubs(searchstring, "en", "English", file_original_path, searchstring_notclean)
            for sub in subtitles_list: append_subtitle(sub)
        if 'eng' not in item['languages'] and 'spa' not in item['languages'] and 'por' not in item['languages']:
            _dialog.notification(_scriptname, 'Only Portuguese | Portuguese Brazilian | English | Spanish.', xbmcgui.NOTIFICATION_ERROR)
            
    def Download(id, filename):
        """Called when subtitle download request from KODI."""
        if os.path.isdir(_temp):shutil.rmtree(_temp)
        xbmcvfs.mkdirs(_temp)
        if not os.path.isdir(_temp):xbmcvfs.mkdir(_temp)
        unpacked = 'ldivx-' + str(uuid.uuid4()).replace("-","")[0:6]
        xbmcvfs.mkdirs(pjoin(_temp,unpacked,''))
        _newtemp = os.path.join(_temp, xbmcvfs.translatePath(unpacked).replace('\\','/'))

        subtitles_list = []
        my_opener = login()
        
        content = my_opener.open(main_url + 'modules.php?name=Downloads&d_op=getit&lid=' + id + '&username=' + _addon.getSetting( 'LDuser' ))
        content = content.read()
        
        raw_text = ""
        try:
            raw_text = content.decode('utf-8')
        except UnicodeDecodeError:
            raw_text = content.decode('ISO-8859-1', errors='replace')

        if 'url=sair.php?referer=login' in raw_text:
            _dialog.notification(_scriptname, _language(32019).encode('utf8'), xbmcgui.NOTIFICATION_ERROR)
            xbmcplugin.endOfDirectory(int(sys.argv[1]))
        if raw_text is not None:
            header = content[:4].decode('latin1', errors='ignore')
            if header == 'Rar!':
                tmp_file = str(uuid.uuid4())+".rar"
                local_tmp_file = pjoin(_temp, tmp_file)
                packed = True
            elif header == 'PK\x03\x04':
                local_tmp_file = pjoin(_temp, str(uuid.uuid4())+".zip")
                packed = True
            else:
                local_tmp_file = pjoin(_temp, "ldivx.srt")
                subs_file = local_tmp_file
                packed = False
            log("Trying to save subtitles to '%s'" % (local_tmp_file,))
            try:
                with open(local_tmp_file, "wb") as local_file_handle:
                    local_file_handle.write(content)
                local_file_handle.close()
                xbmc.sleep(500)
            except:
                log("Failed to save subtitles to '%s'" % (local_tmp_file,))
            if packed:
                try:
                    compressed_file = 'rar://' + quote_plus(local_tmp_file) + '/'
                    log("Will try to extract...")
                    xbmc_extract(compressed_file,_newtemp)
                except:
                    xbmc.executebuiltin("XBMC.Extract(%s, %s)" % (compressed_file, _newtemp), True)
                searchsubs = recursive_glob(_newtemp, SUB_EXTS)
                searchsubscount = len(searchsubs)
                if searchsubscount == 0:
                    dialog = xbmcgui.Dialog()
                    subs_file = dialog.browse(1, _language(32024).encode('utf8'), 'files', '', False, True, _temp + '/')
                    subtitles_list.append(subs_file)
                else:
                    os.remove(local_tmp_file)
                    log("count: '%s'" % (searchsubscount,))
                    for file in searchsubs:
                        if searchsubscount == 1:
                            log("Unpacked subtitles file '%s'" % (file,))
                            try:
                                subs_file = pjoin(_newtemp, file)
                            except:
                                log("Failed to load subtitle file '%s'" % (file,))
                            subtitles_list.append(subs_file)
                            break
                        else:
                            dialog = xbmcgui.Dialog()
                            subs_file = dialog.browse(1, _language(32024).encode('utf8'), 'files', '', False, True, _newtemp + '/')
                            subtitles_list.append(subs_file)
                            break
            else: subtitles_list.append(subs_file)
        return subtitles_list

    def get_params():
        param = []
        paramstring = sys.argv[2]
        if len(paramstring) >= 2:
            params = paramstring
            cleanedparams = params.replace('?', '')
            if params.endswith('/'): params = params[:-2]
            pairsofparams = cleanedparams.split('&')
            param = {}
            for pair in pairsofparams:
                splitparams = {}
                splitparams = pair.split('=')
                if len(splitparams) == 2: param[splitparams[0]] = splitparams[1]
        return param

    # Get parameters from XBMC and launch actions
    params = get_params()

    if params['action'] == 'search' or params['action'] == 'manualsearch':
        item = {}
        item['temp']               = False
        item['rar']                = False
        item['year']               = xbmc.getInfoLabel("VideoPlayer.Year")
        item['season']             = str(xbmc.getInfoLabel("VideoPlayer.Season"))
        item['episode']            = str(xbmc.getInfoLabel("VideoPlayer.Episode"))
        item['tvshow']             = str(xbmc.getInfoLabel("VideoPlayer.TVshowtitle"))
        item['title']              = str(xbmc.getInfoLabel("VideoPlayer.OriginalTitle"))
        item['file_original_path'] = urllib.parse.unquote(xbmc.Player().getPlayingFile())
        item['mansearch'] = False
        item['languages'] = []

        if 'searchstring' in params:
            item['mansearch'] = True
            item['mansearchstr'] = urllib.parse.unquote(params['searchstring'])

        for lang in urllib.parse.unquote(params['languages']).split(','):
            item['languages'].append(xbmc.convertLanguage(lang, xbmc.ISO_639_2))

        if "s" in item['episode'].lower():
            item['season'] = "0"
            item['episode'] = item['episode'][-1:]

        if "http" in item['file_original_path']: item['temp'] = True

        elif "rar://" in item['file_original_path']:
            item['rar'] = True
            item['file_original_path'] = os.path.dirname(item['file_original_path'][6:])

        elif "stack://" in item['file_original_path']:
            stackPath = item['file_original_path'].split(" , ")
            item['file_original_path'] = stackPath[0][8:]

        Search(item)

    elif params['action'] == 'download':
        subs = Download(params["id"], params["filename"])
        for sub in subs:
            listitem = xbmcgui.ListItem(label=sub)
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=sub, listitem=listitem, isFolder=False)

    xbmcplugin.endOfDirectory(int(sys.argv[1]))
