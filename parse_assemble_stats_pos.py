#!/usr/bin/env python

import sys
from os import path
from lxml import etree
from StringIO import StringIO
from nltk.stem.porter import PorterStemmer
from nltk.tokenize.punkt import PunktSentenceTokenizer, PunktParameters
from nltk.corpus import stopwords
from math import log
import nltk
import nltk.data
from string import punctuation
import re
from counter import Counter
import pyparsing

tagset_location = path.join('tagset.txt')
tagset = set()
re_punct = re.compile(r'[^\w\s]+')
omit_redirect = False
perform_stemming = False
stemmer = PorterStemmer()
sent_tokenize = nltk.data.load(path.join('tokenizers','punkt','english.pickle'))
stops = set(stopwords.words("english"))
total_sentences = 0
total_chars_kept_tokens = 0
total_tokens = 0
total_types = 0
total_docs = 0
next_doc_id = 0
idf_denom_offset = 0.1
# term, doc -> # times appear
term_freq = {}
# term, doc -> tf-idf value
tf_idf = {}
# doc_id -> raw text
raw_docs = {}
# doc_id -> list processed tokens
docs = {}
# doc_id -> tag-counter-dict
doc_tags = {}
# for each entence, store (text, tag counter)
# doc_id -> list (text, tag-counter-dict)
doc_sents = {}
# stats[doc_id] = (num_types, num_kept_tokens, num_sentences, num_chars_kept_tokens):
stats = {}
dfs = {}
tfidfs = {}

def get_docfreq(term):
    # go through all documents
    # see how many have (term, doc) key in term_freqs
    if term not in dfs:
        total = 0
        for d in docs:
            if (term, d) in term_freq and term_freq[(term,d)]:
                total += 1
        dfs[term] = total
    #print >> sys.stderr, 'df(%s): %s' % (term, dfs[term])
    return dfs[term]

def get_total_tfidf(term):
    # go through all docs
    if term not in tfidfs:
        total = 0.0
        log_modifier = 0
        df = get_docfreq(term)
        if df == 0:
            tfidfs[term] = 0
        else:
            if df > 1:
                log_modifer = df - 1
            for d in docs:
                if (term, d) in tf_idf:
                    if df == 1: # add our one total and break
                        total += term_freq[(term,d)]
                        break
                    else: # add to weighted avg, to avoid bias towards long docs
                        total += term_freq[(term,d)] / len(docs[d])
            tfidfs[term] = total * log( float(total_docs - log_modifier) / float(df - log_modifier + idf_denom_offset),10)
    return tfidfs[term]

def compute_tfidf(term, doc):
    global total_docs, idf_denom_offset
    tf = float(term_freq[(term, doc)])
    df = get_docfreq(term)
    idf = log(float(total_docs) / float(df + idf_denom_offset),10)
    #print >> sys.stderr, 'term:%s doc:%s' % (term, doc)
    #print >> sys.stderr, 'tf:%s df:%s idf:%s' % (tf, df, idf)
    return tf * idf

def compute_all_tfidf():
    #  calc term doc values
    for (term, doc) in term_freq.keys():
        if (term,doc) not in tf_idf:
            tf_idf[(term,doc)] = compute_tfidf(term, doc)
    # calc total term values
    for (term,doc) in term_freq.keys():
        # already deals with duplicates
        get_total_tfidf(term)

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

# accepts iterable of tokens
# returns list of stemmed tokens, dict of found types, number of characters in orig text
def stem_tokens_stopwords(tokens, use_stops = True):
    stemmed = []
    types = {}
    num_chars_kept_tokens = 0
    for t in tokens:
        if use_stops and t in stops:
            continue
        # exclude from tokens if it's only punctuation
        # test different match modes?
        if (len(t) == 1 and (t[0] in punctuation or t in punctuation)) or re_punct.match(t):
            continue
        if perform_stemming:
            s = stemmer.stem(t)
        else:
            s = t
        stemmed.append(s)
        if s not in types:
            types[s] = 1
        num_chars_kept_tokens += len(t)
    return stemmed, types, num_chars_kept_tokens

# need to get num tokens, num types, avg sentence length in words, in chars
def process_text(text):
    global next_doc_id, total_docs, total_sentences, total_chars_kept_tokens, total_tokens
    # label unique doc id
    doc_id = next_doc_id
    next_doc_id += 1
    # get tokens from text
    text = text.lower() # convert to lowercase
    # TODO parse text, replace all instances of '[[...]]' and the like


    tokens = nltk.word_tokenize(text)
    # get tokens / types after stemming and eliminating stopwords
    # list of stemmed tokens, dict of found types, number of characters in orig tokens
    stems, types, num_chars_kept_tokens = stem_tokens_stopwords(tokens)
    num_types = len(types.keys())
    num_kept_tokens = 0 # could do len(stems) but have to iterate through it anyway
    # populate term frequencies
    for t in stems:
        term_freq[(t,doc_id)] = term_freq.get((t,doc_id), 0)
        term_freq[(t, doc_id)] += 1
        num_kept_tokens += 1
    # calculate sentence stats
    # tokenize text into sentences
    sentences = sent_tokenize.tokenize(text)
    num_sentences = 0
    # pos tag distribution
    num_verbs = 0
    num_nouns = 0
    doc_sents[doc_id] = [] # for each sentence, store (text, tag counter)
    doc_tags[doc_id] = Counter()
    #print >> sys.stderr'sentences:'
    for s in sentences:
        #print >> sys.stderrs, '\n'
        # compute num verbs, num nouns feature
        # tokenize the sentences to prep for POS tagging
        sent_tokens = nltk.word_tokenize(s)
        pos = nltk.pos_tag(sent_tokens)
        tag_dist = Counter([tag for word,tag in pos])
        #print >> sys.stderrtag_dist
        #print >> sys.stderrsorted(tag_dist)
        doc_sents[doc_id].append((s, tag_dist))
        doc_tags[doc_id].update(tag_dist)
        num_sentences += 1
    # save stats and info for document
    stats[doc_id] = (num_types, num_kept_tokens, num_sentences, num_chars_kept_tokens)
    raw_docs[doc_id] = text
    docs[doc_id] = stems # list of stems, after excluding stopwords
    #print >> sys.stderrdocs[doc_id]
    # and track global stats
    total_docs += 1
    total_sentences += num_sentences
    total_chars_kept_tokens += num_chars_kept_tokens
    total_tokens += num_kept_tokens

def get_page_text(page_elem, ns, rawtextfile):
    # each page has a revision child tag, revision has ID and text
    rev = [i for i in page_elem.iterchildren('{%s}revision' % ns)][0]
    id = [i for i in rev.iterchildren('{%s}id' % ns)][0]
    text = [t for t in rev.iterchildren('{%s}text' % ns)][0]
    #print >> sys.stderr, 'page id:%s\ntext:\n%s' % (id, text.text)
    if text.text is not None:
        t = text.text.encode('utf-8')
        rawtextfile.write('\n')
        rawtextfile.write(t)
        rawtextfile.write('\n')
        rawtextfile.flush()
        # and process the text
        process_text(t)

def main():
    if len(sys.argv) != 3:
        print >> sys.stderr, """usage: %s [xml-file] [plaintext-file]
This script extracts all plain text from the Wikipedia XML file and writes to the desired text file.
It also analyzes and computes data for features.
""" % (sys.argv[0])
        sys.exit()
    load_tagset()
    rawtextfile = open(sys.argv[2], 'w')
    # read all data and write to output file
    f = open(sys.argv[1], 'r')
    xml = f.read()
    fast_iterparse(StringIO(xml), get_page_text, rawtextfile)
    rawtextfile.close()
    # now that we've parsed and processed, compute tf-idf
    compute_all_tfidf()
    # and print results
    for d in sorted(docs):
        print_stats(d)
    #print >> sys.stderr'tfidfs by (term,doc)'
    #for (term,doc) in tf_idf:
    #    print >> sys.stderr'(%s, %s) -> %s' % (term, doc, tf_idf[(term, doc)])
    #print >> sys.stderr'tfidfs by term'
    #for term in tfidfs:
    #    #print >> sys.stderr'(%s) -> %s' % (term, tfidfs[term])

def print_stats(doc):
    #print >> sys.stderr'\nstats for docid:%s' % (doc)
    #print >> sys.stderr'text:\n%s' % raw_docs[doc]
    (num_types, num_kept_tokens, num_sentences, num_chars_kept_tokens) = stats[doc]
    avg_len_sent_words = float(num_kept_tokens) / float(num_sentences)
    avg_len_sent_chars = float(num_chars_kept_tokens) / float(num_sentences)
    avg_word_length = float(num_chars_kept_tokens) / float(num_kept_tokens)
    wt_avg_word_length_tfidf = calc_wt_avg_tfidf_tokens(docs[doc])
    # doc_sents[doc] = list of (text, tag dict) tuples
    sentences_list = [text for (text,tag_dict) in doc_sents[doc]]
    wt_avg_sent_length_tfidf = calc_wt_avg_tfidf_text(' '.join(sentences_list), len(sentences_list))
    data = (num_types, num_kept_tokens, num_sentences, num_chars_kept_tokens, avg_len_sent_words, avg_len_sent_chars, avg_word_length, wt_avg_word_length_tfidf, wt_avg_sent_length_tfidf)
    #print >> sys.stderr'num types:%d num kept tokens:%d\nnum sentences:%d num chars:%d\navg len sents by word:%f\navg len sents by char:%f\navg word len:%f\nwt_avg_word_len_tfidf:%f\nwt_avg_sent_len_tfidf:%f\n' % data
    sys.stdout.write('%s ' % doc)
    for index, value in enumerate(data):
        sys.stdout.write('%s:%s ' % (index, value))
    # document POS tag totals, sorted
    pos_tags = get_pos_feature_str(doc_tags[doc], len(data))
    sys.stdout.write(pos_tags)
    sys.stdout.write('\n')
    sys.stdout.flush()

def load_tagset():
    for line in open(tagset_location, 'r'):
        tokens = line.strip().split()
        tagset.add(tokens[1])

def get_pos_feature_str(counter, feature_starting_index):
    # given a counter, add the other elements to the counter map that are blank.
    # in sorted order, emit (ft_index : count) pairs
    # return string to be appended to the feature vector
    return ' '.join(['%s:%d' % (index + feature_starting_index, counter[tag]) for index, tag in enumerate(sorted(tagset))])

def calc_wt_avg_tfidf_text(text, denom = None):
    # split into tokens
    text = text.lower() # convert to lowercase
    tokens = nltk.word_tokenize(text)
    return calc_wt_avg_tfidf_tokens(tokens, denom)

def calc_wt_avg_tfidf_tokens(tokens, denom = None):
    # stem each token
    stems = stem_tokens_stopwords(tokens)[0]
    total = 0
    # get tfidf of each token
    for word in stems:
        total += get_total_tfidf(word)
    # calculate avg and return
    if denom is None:
        return float(total) / float(len(stems))
    else:
        return float(total) / float(denom)


if __name__ == "__main__":
    main()
