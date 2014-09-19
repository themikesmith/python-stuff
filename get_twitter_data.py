#!/usr/bin/env python

import tweepy, sys, re, os
from datetime import datetime
from time import strftime, sleep
from httplib import HTTPException
from copy import deepcopy

re_handle = re.compile(r'^@[A-Za-z0-9_]{1,15}$')
results_dir = 'twitter_results'
timeline_max = 3200
max_per_timeline_access = 200
rate_limit_timeout = 15
max_http_attempts = 3
max_depth = 1

def sleep_progress(seconds):
    timeSlept = 0
    while(timeSlept < seconds):
        sleep(1)
        if timeSlept % 30 == 0:
            sys.stderr.write('.')
            sys.stderr.flush()
        timeSlept = timeSlept + 1
    sys.stderr.write('\n')
    sys.stderr.flush()

def usage():
    print """This script gathers corpora from each user who has replied to the handle(s) listed.
    usage: %s [file_list_handles]
where [file_list_handles] is a file that lists handles to use as roots of the tree.
The script performs a search to a depth of 2, outputting corpora for each user found.
""" % sys.argv[0]
    sys.exit()

def login():
    api_key = 'LJp2HGmTfj2WezyD44YwKpGvj'
    api_secret = 'EVXX1KGvO4xyXkRkRn3ObjUNQ0OTUJlRHwrmGznH5nfLL5Rtdy'
    access_token = '2577511033-Y6M6xsyaSdyJheXnhHYZucu1wEIaMJs9IwRKYQz'
    access_secret = 'KKuaQ19d7nxbouxt0x8HGSV5TtMiYkddbI9JzLSXJwn6U'
    auth = tweepy.OAuthHandler(api_key, api_secret)
    auth.set_access_token(access_token, access_secret)
    api = tweepy.API(auth)
    #api.update_status('hey everyone! it is now ' + datetime.now().strftime('%Y-%m-%d %I:%M:%S %p'))
    return api

def get_all_users_mentioned_replied(api, handle, users):
    # get all tweets
    tweets = get_all_tweets(api, handle)
    # get users mentioned
    for tweet in tweets:
        for user in tweet.entities['user_mentions']:
            idstr = user['id_str']
            if idstr not in users:
                users[idstr] = user['screen_name']
                print >> sys.stderr, 'found user:%s (%s)' % (user['screen_name'], user['id_str'])
            else:
                print >> sys.stderr, 'duplicate:%s (%s)' % (user['screen_name'], user['id_str'])
        replied_user = tweet.in_reply_to_user_id_str
        replied_handle = tweet.in_reply_to_screen_name
        if replied_user is not None and replied_handle is not None:
            if replied_user not in users:
                users[replied_user] = replied_handle
                print >> sys.stderr, 'found user:%s (%s)' % (replied_handle, replied_user)
            else:
                print >> sys.stderr, 'duplicate:%s (%s)' % (replied_handle, replied_user)
    return users

def get_all_tweets(api, handle, id_str = None, max = None, max_id = None, num_attempts = 0):
    print >> sys.stderr, 'getting timeline for user %s (%s) maxid:%s' % (handle, id_str, max_id)
    tweets = []
    if num_attempts > max_http_attempts:
        return tweets
    # tweets might be protected
    try:
        newtweets = []
        if id_str is not None:
            newtweets = api.user_timeline(id_str = id_str, count = max_per_timeline_access, max_id = max_id)
        else:
            newtweets = api.user_timeline(screen_name = handle, count = max_per_timeline_access, max_id = max_id)
        tweets.extend(newtweets)
        if not len(tweets):
            return tweets
        oldest = tweets[-1].id
        max_id = oldest - 1
        while(len(newtweets)):
            #print >> sys.stderr, 'getting tweets before id:%s' % str(oldest)
            newtweets = api.user_timeline(screen_name = handle, max_id = max_id, count = max_per_timeline_access)
            tweets.extend(newtweets)
            oldest = tweets[-1].id
            max_id = oldest - 1
            print >> sys.stderr, '%d tweets downloaded so far. max_id:%s' % (len(tweets), max_id)
            if max is not None and len(tweets) > max:
                break
    except HTTPException as e:
        print >> sys.stderr, "error when getting timeline for user %s (%s) :: %s" % (handle, id_str, e)
        sleep_progress(60)
        print >> sys.stderr, 'retrying from %s' % (max_id)
        num_attempts = num_attempts + 1
        tweets.extend(get_all_tweets(api, handle, id_str, None, max_id, num_attempts))
    except tweepy.error.TweepError as e:
        print >> sys.stderr, "error when getting timeline for user %s (%s) :: %s" % (handle, id_str, e)
        if "rate limit" in str(e).lower():
            # reattempt if hit rate limit
            print >> sys.stderr, 'waiting about %s minutes, then retrying.  it\'s now %s ...' % (rate_limit_timeout, strftime("%H:%M:%S"))
            sleep_progress(65*(rate_limit_timeout))
            print >> sys.stderr, 'it\'s %s - retrying from %s' % (strftime("%H:%M:%S"), max_id)
            num_attempts = num_attempts + 1
            tweets.extend(get_all_tweets(api, handle, id_str, None, max_id, num_attempts))
    return tweets

def main():
    if len(sys.argv) != 2:
        usage()
    # make results directory
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    # id_str -> screen_name
    # track id and handle for more exact searching
    roots = {} # ingest tree roots - twitter handles
    users = {} # for storing users whose corpora to download
    for line in open(sys.argv[1], 'r'):
        line = line.strip()
        if not len(line):
            continue
        if re_handle.match(line):
            roots[line] = line # we don't have id yet
        else:
            print >> sys.stderr, 'invalid handle from file:%s' % line

    api = login()
    depth = 0
    old_roots = {}
    while depth < max_depth:
        # get all tweets and replies from each user in question
        for id,handle in roots.items():
            if id not in old_roots:
                print >> sys.stderr, 'depth:%s handle:%s' % (depth, handle)
                users = get_all_users_mentioned_replied(api, handle, users)
        depth = depth + 1
        if depth < max_depth: # prep for next iteration - use new users found as roots
            old_roots.update(roots)
            roots = deepcopy(users)

    reload(sys)
    sys.setdefaultencoding('utf-8')

    for id_str, handle in users.items():
        # create filename for output file
        filename = re.sub(r'@', '', handle.lower()) + '.txt'
        outfile = open(os.path.join(results_dir, filename), 'w')
        # get all tweets available
        tweets = get_all_tweets(api, handle, id_str)
        # assemble corpus
        for tweet in tweets:
            print >> outfile, repr(tweet.text)
        outfile.flush()
        outfile.close()

if __name__=='__main__':
    main()
