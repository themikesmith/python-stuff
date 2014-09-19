#!/usr/bin/env python

from bs4 import BeautifulSoup
import requests
from urlparse import urlparse, urljoin
import sys
import re
import time
import os
import shutil
import mimetypes
from socket import error

max_get_retries = 5

def make_request(url = None, retries = 0, stream = False):
    r = None
    try:
        r = requests.get(url, stream = stream)
        return r
    except (requests.exceptions.RequestException, socket.error) as e:
        print >> sys.stderr, 'error when requesting url:\n%s' % repr(e)
        if retries < max_get_retries:
            print >> sys.stderr, 'attempts:%d - retrying...' % retries
            return make_request(url, retries = (retries + 1), stream = stream)
        else:
            print >> sys.stderr, 'max retries exceeded'
    return r # else return None

def save_file(resultsdir, r, scheme, url, file_ending, file_open_flag, ctype, cset):
    # second, save the file
    # make output file from url
    # remove scheme info
    scheme_remove = ''.join([scheme, after_scheme])
    url_noscheme = re.sub(re.escape(scheme_remove), '', url)
    # and all weird chars
    filename = re.sub(r'\W', '_', url_noscheme)
    filename = filename + file_ending
    # then create the valid file, open empty for writing
    try:
        outfile = open(os.path.join(resultsdir, filename), file_open_flag)
        if ctype.startswith('text'):
            if cset is not None:
                reload(sys)
                sys.setdefaultencoding(cset)
            else:
                reload(sys)
                sys.setdefaultencoding("utf-8")
            #print >> outfile, r.text
            # prettify and parse then print it
            soup = BeautifulSoup(r.text, 'html5lib')
            [s.extract() for s in soup(['style', 'script', 'a', 'href'])]
            print >> outfile, soup.prettify(cset).encode(cset)
        else:
            r = make_request(url, stream=True)
            #r = requests.get(url, stream=True)
            shutil.copyfileobj(r.raw, outfile)
            del r
        # flush outfile
        outfile.flush()
    except IOError as e:
        print >> sys.stderr, 'IOError %s : %s' % (e.errno, e.strerror)
    finally:
        outfile.close()

# verify number args
if len(sys.argv) != 3:
    print >> sys.stderr, """Usage:
    %s [url_list] [urls_never_crawl]
where [url_list] is a list of base urls to crawl, one per line
and [urls_never_crawl] is a list of urls never to crawl, one per line.
Note that the script prints progress to stderr, and that one may pipe stderr to its own file, like the following
    %s [url_list] [urls_never_crawl] 2> [error_file]
for ease of analysis.
""" % (sys.argv[0], sys.argv[0])
    sys.exit()
# first arg is the list of base urls to crawl, one per line
list_crawl_urls = []
for line in open(sys.argv[1], 'r'):
    l = line.strip()
    if len(l) > 0:
        list_crawl_urls.append(l)
# second is the list of urls to never crawl
urls_never_crawl = []
for line in open(sys.argv[2], 'r'):
    urls_never_crawl.append(line.strip())

codecs = ['utf-8','iso-8859-1', 'us-ascii']
re_pdf = re.compile(r'application/p(?:df|s)')
re_msword = re.compile(r'application/msword')
re_texthtml = re.compile(r'text/html')
re_audio = re.compile(r'audio/')
re_faq = re.compile(r'frequently\Wasked\Wquestions|faq|q\W?and\W?a')
re_image = re.compile(r'image/')

# create results directory
resultsdir = 'results'
qa_dir = 'qa_dir'
if not os.path.exists(resultsdir):
    os.makedirs(resultsdir)
if not os.path.exists(qa_dir):
    os.makedirs(qa_dir)

for url in list_crawl_urls:
    # get base url and base hostname, for detecting locality
    # and output file for this url
    p = urlparse(url)
    scheme = p.scheme
    after_scheme = '://'
    base_host = p.hostname
    base_path = p.path
    if base_host is None:
        print >> sys.stderr, 'error parsing base url! %s' % url
        sys.exit()
    #print >> sys.stderr, 'scheme:%s' % scheme
    #print >> sys.stderr, 'host:%s' % base_host
    #print >> sys.stderr, 'path:%s' % base_path
    base_url = ''.join([scheme, after_scheme, base_host, base_path])
    print >> sys.stderr, 'base url:\n%s' % base_url
    # re's for checking locality, pdf type, and text type
    re_base = re.compile(re.escape(base_url))

    # make local copy of urls to avoid
    local_urls_never_crawl = [u for u in urls_never_crawl if base_url_noscheme in u]
    #print >> sys.stderr, 'local lists!'
    #print >> sys.stderr, local_urls_never_crawl
    scheme_remove = ''.join([scheme, after_scheme])
    url_noscheme = re.sub(re.escape(scheme_remove), '', url)
    # and all weird chars
    url_dir = re.sub(r'\W', '_', url_noscheme)
    url_results_dir = os.path.join(resultsdir, url_dir)
    url_qa_dir = os.path.join(qa_dir, url_dir)
    if not os.path.exists(url_results_dir):
        os.makedirs(url_results_dir)

    # track sites we've seen before - dict for efficiency
    seen = {}
    # list of sites
    sites = []

    sites.append(url)
    seen[url] = 1
    num = 0
    num_tokens = 0
    #max = 140
    #while(len(sites) < max and sites):
    while(sites):
        url = sites.pop()
        num = num + 1
        time.sleep(2)
        print >> sys.stderr, '\n\nurl %d : %s' % (num, url)
        p = urlparse(url)
        # only pursue links that are local to the base host name
        if p.hostname != base_host:
            #print >> sys.stderr, 'not local!'
            continue
        r = make_request(url)
        #r = requests.get(url)

        file_open_flag = 'wb'

        # first check content type, exclude audio, parse html
        if 'content-type' not in r.headers:
            continue
        ctype = r.headers['content-type']
        #print >> sys.stderr, 'ctype: %s' % ctype
        m = re.search(r'; ?charset=([-\w]+?)$', ctype)
        cset = 'utf-8'
        if m:
            cset = m.group(1)
            if cset.lower() not in codecs:
                print >> sys.stderr, 'char set:%s' % cset
        ctype = re.sub(r'; ?charset=[-\w]+?$', '', ctype)
        file_ending = mimetypes.guess_extension(ctype)
        #if file_ending is None:
        #    print >> sys.stderr, 'none file ending: ctype:%s' % ctype
        #print >> sys.stderr, 'ext: %s' % file_ending
        m = re_pdf.match(ctype)
        n = re_audio.match(ctype)
        o = re_texthtml.match(ctype)
        p = re_msword.match(ctype)
        q = re_image.match(ctype)

        soup = None
        isqa = False

        #if m:
        #    # save them
        #    #print >> sys.stderr, 'saving pdf...'
        #elif n:
        if n:
            #print >> sys.stderr, 'skip audio...'
            continue
        elif q:
            #print >> sys.stderr, 'skip images...'
            continue
        elif o:
            data = r.text
            # parse the site's data, finding new links and extracting tokens
            # parse with different parsers - different handling of malformed html
            soup = BeautifulSoup(data, 'html5lib')
            wordcount = {}

            # first find all new links to follow...
            for link in soup.find_all('a'):
                href = link.get('href')
                if href is None:
                    continue
                #print >> sys.stderr, 'href:%s' % href
                # parse this, exclude non-local links
                parse = urlparse(href)
                #print >> sys.stderr, 'hostname:%s' % parse.hostname
                if parse.hostname is not None and parse.hostname != base_host:
                    #print >> sys.stderr, 'not local by hostname...'
                    continue
                # if the hostname is None, it's a local link that needs to be joined with the base
                if parse.hostname is None:
                    # however, we exclude self-referencing links
                    if '#' in href:
                        continue
                    full = urljoin(base_url, href)
                else: # or it's a local full link
                    full = href
                # now verify that the links are web links
                # this excludes things like 'mailto:' etc
                m = re_base.match(full)
                if not m:
                    #print >> sys.stderr, 'not local by match...'
                    continue
                # and if we haven't seen it, mark it as such and add it to the list
                if full not in seen:
                    seen[full] = 1
                    # if full starts with any of the urls, exclude
                    if any([full.startswith(x) for x in local_urls_never_crawl]):
                        #print >> sys.stderr, 'url excluded: %s' % full
                        continue
                    sites.append(full)
                    #print >> sys.stderr, 'new : %s' % full
                    #print >> sys.stderr, 'number seen:%d' % len(sites)
            title_elem = soup.find('title')
            if title_elem is not None:
                title = title_elem.text.lower()
                m = re_faq.search(title)
                if m:
                    # save copy in question folder
                    isqa = True
        elif not o and not m and not p:
            # if it isn't text, print a note that we may need to handle this type
            print >> sys.stderr, '\nnew content type:%s\n' % ctype
            #file_open_flag = 'wb'
            #file_ending = re.sub(r'\W', '-', ctype)
        # also check url
        m = re_faq.search(url)
        if m or isqa:
            print >> sys.stderr, 'qa doc! %s' % url
            if not os.path.exists(url_qa_dir):
                os.makedirs(url_qa_dir)
            save_file(url_qa_dir, r, scheme, url, file_ending, file_open_flag, ctype, cset)
        save_file(url_results_dir, r, scheme, url, file_ending, file_open_flag, ctype, cset)

# done!
print >> sys.stderr, 'finished!'
