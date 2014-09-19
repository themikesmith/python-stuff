#!/usr/bin/env python

import sys
from lxml import etree
from StringIO import StringIO
from nltk.stem.porter import PorterStemmer
from nltk.tokenize.punkt import PunktSentenceTokenizer, PunktParameters
from nltk.corpus import stopwords
import nltk
import nltk.data

omit_redirect = False
stemmer = PorterStemmer()
sent_tokenize = nltk.data.load('tokenizers/punkt/english.pickle')
total_sentences = 0
total_chars = 0
total_tokens = 0
total_types = 0
total_docs = 0
next_doc_id = 0
# term, doc -> # times appear
term_freqs = {}

# from http://www.ibm.com/developerworks/library/x-hiperfparse/index.html
# optimized memory-aware iterparsing with lxml
def fast_iterparse(file, function, rawtextfile):
    number = 0
    namespaces = {}
    #for event, elem in etree.iterparse(file, events=("end", "start-ns", "end-ns")):
    for event, elem in etree.iterparse(file, events=("end", "start-ns")):
        #if number > max:
        #    break
        if event == 'start-ns':
            #print >> sys.stderr, 'start! ns prefix:%s ns:%s' % (elem[0], elem[1])
            namespaces[elem[0]] = elem[1]
        #elif event == 'end-ns':
        #    #print >> sys.stderr, 'end! ns prefix:%s ns:%s' % (elem[0], elem[1])
        else:
            #print >> sys.stderr, 'current elem:%s' % elem.tag
            if elem is None:
                continue
            if elem.tag == '{%s}page' % namespaces['']:
                #print >> sys.stderr, '\n\ncurrent page:%s' % elem.tag
                # verify no redirect subtag
                redirect = False
                if omit_redirect:
                    for i in elem.iterchildren():
                        #print >> sys.stderr, '%s' % i.tag
                        if i.tag == '{%s}redirect' % namespaces['']:
                            redirect = True
                            #print >> sys.stderr, 'redirect found!'
                            break
                if not redirect:
                    function(elem, namespaces[''], rawtextfile)
                    number += 1
                #else:
                #    #print >> sys.stderr, 'omitting page with redirect'
            # TODO iterparse doesn't actually go serially?
            # so you can't clear previous elements...
            #elem.clear()
            #while elem.getprevious() is not None:
            #    del elem.getparent()[0]

def get_page_text(page_elem, ns, rawtextfile):
    # each page has a revision child tag, revision has ID and text
    rev = [i for i in page_elem.iterchildren('{%s}revision' % ns)][0]
    id = [i for i in rev.iterchildren('{%s}id' % ns)][0]
    text = [t for t in rev.iterchildren('{%s}text' % ns)][0]
    #print >> sys.stderr, 'page id:%s\ntext:\n%s' % (id, text.text)
    if text.text is not None:
        rawtextfile.write('\n')
        rawtextfile.write(text.text.encode('utf-8'))
        rawtextfile.write('\n')
        rawtextfile.flush()

def main():
    if len(sys.argv) != 3:
        print >> sys.stderr, """usage: %s [xml-file] [plaintext-file]
This script extracts all plain text from the Wikipedia XML file
and writes to the desired text file
""" % (sys.argv[0])
        sys.exit()
    rawtextfile = open(sys.argv[2], 'w')
    # read all data and write to output file
    f = open(sys.argv[1], 'r')
    xml = f.read()
    fast_iterparse(StringIO(xml), get_page_text, rawtextfile)
    rawtextfile.close()

if __name__ == "__main__":
    main()
