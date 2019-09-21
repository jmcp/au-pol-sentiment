#!/usr/bin/env python3.7

#
# Copyright (c) 2019, James C. McPherson. All Rights Reserved.
#

# Available under the terms of the MIT license:
#
# Permission is hereby granted, free of charge, to any
# person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the
# Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the
# Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice
# shall be included in all copies or substantial portions of
# the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
# KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
# OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# This work draws in part upon the blog post
# http://blog.chapagain.com.np/python-nltk-twitter-sentiment-analysis-natural-language-processing-nlp/
# Thankyou to @chapagain for getting me started

import datetime
import json
import os
import re
import string
import sys
import time

from flask import Flask, make_response, render_template, request
#from flask_cors import CORS, cross_origin
from nltk.corpus import (twitter_samples, stopwords)
from nltk.tokenize import TweetTokenizer
from nltk.stem import PorterStemmer
from nltk import classify
from nltk import NaiveBayesClassifier

from random import shuffle
from twython import Twython

from urllib.parse import quote
from wtforms import Form, SelectField


__doc__ = """

This is a Flask application. The user chooses a hashtag from a
dropdown list of Australian politics-related tags, the application
retrieves tweets using Twitter's standard search API (which limits
results to 100) and we analyze the sentiment in those tweets. This
sentiment data is rendered with Chart.js and refreshed every 30
seconds. The latency is to avoid hitting Twitter's rate limit for
their standard API.

"""

usagestr = """

Run this with Flask.

"""


consumer_key = ""
consumer_secret = ""
access_token = ""
access_token_secret = ""

tweet_tokenizer = TweetTokenizer(preserve_case=False, strip_handles=True, reduce_len=True)
stemmer = PorterStemmer()
stopwords_english = stopwords.words('english')

        
# Happy Emoticons
emoticons_happy = set([
    ':-)', ':)', ';)', ':o)', ':]', ':3', ':c)', ':>', '=]', '8)', '=)', ':}',
    ':^)', ':-D', ':D', '8-D', '8D', 'x-D', 'xD', 'X-D', 'XD', '=-D', '=D',
    '=-3', '=3', ':-))', ":'-)", ":')", ':*', ':^*', '>:P', ':-P', ':P', 'X-P',
    'x-p', 'xp', 'XP', ':-p', ':p', '=p', ':-b', ':b', '>:)', '>;)', '>:-)',
    '<3'
    ])
 
# Sad Emoticons
emoticons_sad = set([
    ':L', ':-/', '>:/', ':S', '>:[', ':@', ':-(', ':[', ':-||', '=L', ':<',
    ':-[', ':-<', '=\\', '=/', '>:(', ':(', '>.<', ":'-(", ":'(", ':\\', ':-c',
    ':c', ':{', '>:\\', ';('
    ])
 
# all emoticons (happy + sad)
emoticons = emoticons_happy.union(emoticons_sad)


def clean_tweets(tweet):
    # remove stock market tickers like $GE
    tweet = re.sub(r'\$\w*', '', tweet)
    # remove old style retweet text "RT"
    tweet = re.sub(r'^RT[\s]+', '', tweet) 
    # remove hyperlinks
    tweet = re.sub(r'https?:\/\/.*[\r\n]*', '', tweet)
    # remove hashtags
    # only removing the hash # sign from the word
    tweet = re.sub(r'#', '', tweet)
    # tokenize tweets
    tokenizer = TweetTokenizer(preserve_case=False, strip_handles=True, reduce_len=True)
    tweet_tokens = tokenizer.tokenize(tweet)
    tweets_clean = []    
    for word in tweet_tokens:
        if (word not in stopwords_english and # remove stopwords
              word not in emoticons and # remove emoticons
                word not in string.punctuation): # remove punctuation
            stem_word = stemmer.stem(word) # stemming word
            tweets_clean.append(stem_word) 
    return tweets_clean


# feature extractor function
def bag_of_words(tweet):
    words = clean_tweets(tweet)
    words_dictionary = dict([word, True] for word in words)    
    return words_dictionary


class ChooserForm(Form):
    hashtag = SelectField("Hashtag to follow",
                          choices=[("auspol", "Australian Politics"),
                                   ("actpol", "Australian Capital Territory"),
                                   ("nswpol", "New South Wales"),
                                   ("ntpol", "Northern Territory"),
                                   ("qldpol", "Queensland"),
                                   ("sapol", "South Australia"),
                                   ("taspol", "Tasmania"),
                                   ("vicpol", "Victoria"),
                                   ("wapol", "Western Australia")])

    
def get_creds():
    """Read keys and secrets from the creds file"""
    global consumer_key, consumer_secret, access_token, access_token_secret
    app.config.from_pyfile("creds.conf")
    consumer_key = app.config["CONSUMER_API_KEY"]
    consumer_secret = app.config["CONSUMER_API_SECRET"]
    access_token = app.config["ACCESS_TOKEN_KEY"]
    access_token_secret = app.config["ACCESS_TOKEN_SECRET"]
    if consumer_key == "" or consumer_secret == "":
        print("Consumer key/secret cannot be empty")
        #sys.exit(1)
    if access_token == "" or access_token_secret == "":
        print("Access token/secret cannot be empty")
        #sys.exit(1)


# boilerplate and basic setup
app = Flask("au-pol-sentiment")
get_creds()

twitter = Twython(consumer_key, consumer_secret,
                  access_token, access_token_secret)

# Set up the positive and negative sentiment sets
# positive tweets feature set
pos_tweets_set = []
for tweet in twitter_samples.strings('positive_tweets.json'):
    pos_tweets_set.append((bag_of_words(tweet), 'pos'))    
 
    # negative tweets feature set
neg_tweets_set = []
for tweet in twitter_samples.strings('negative_tweets.json'):
    neg_tweets_set.append((bag_of_words(tweet), 'neg'))

# Randomize, a little
shuffle(pos_tweets_set)
shuffle(neg_tweets_set)

# start training
test_set = pos_tweets_set[:1000] + neg_tweets_set[:1000]
train_set = pos_tweets_set[1000:] + neg_tweets_set[1000:]
classifier = NaiveBayesClassifier.train(train_set)


def update(inhashtag, lastid):
    hashtag = "#" + inhashtag
    results = {}
    data = list()
    data.append('data1')
    labels = list()
    # Note: the free search API gives us a max of 100 results
    tw = twitter.search(q=hashtag, result_type="recent", since_id=lastid)
    if len(tw["statuses"]) > 0:
        lastid = tw["statuses"][-1]["id"]
        results["lastid"] = lastid
        for tweet in tw["statuses"]:
            url = "https://twitter.com/" + tweet["user"]["screen_name"]
            url += "/status/" + str(tweet["id"])
            probres = classifier.prob_classify(bag_of_words(tweet["text"]))
            # Create an ISO-like timestamp, without UTC offset
            tstamp = datetime.datetime.strptime(
                tweet["created_at"],
                "%a %b %d %H:%M:%S %z %Y").isoformat()[0:-6]
            labels.append("""moment("{stamp}")""".format(stamp=tstamp))
            # This is *ugly* because we don't want the actual data points to
            # be jsonified as it passes through the gateway. Sorry.
            #datafmt = """'x': moment({stamp}, "\%x"), 'y': {value}"""
            #data.append("{" + datafmt.format(
            #    stamp=tstamp,value=100 * probres.prob("pos")) + "}")
            data.append(str(int(100 * probres.prob("pos"))))
    else:
        print("No data returned in the last 30 seconds")        
    results["chartdata"] = data
    results["labels"] = labels
    results["lastid"] = lastid
    return results

    
@app.route("/sentiment", methods=("POST", "GET"))
def sentiment():
    # print("With associated Request\n{req}".format(req=dir(request)))
    # print("remote addr {0}".format(request.remote_addr),
    #      "url {0}".format(request.url),
    #      "host_url {0}".format(request.host_url),
    #      "headers\n{0}".format(request.headers),
    #      "args {0}".format(request.args))
    # queries the hashtag, translates
    if request.method == "GET":
        hashtag = request.args["hashtag"]
        lastid = request.args["lastid"]
    else:
        formdict = request.form.to_dict()
        hashtag = formdict["hashtag"]
        if "lastid" in formdict:
            lastid = formdict["lastid"]
        else:
            lastid = ""
    sentiments = update(hashtag, lastid)
    if request.method == "GET":
        return json.dumps(sentiments)
    
    resp = make_response(
        render_template("sentiment.html",
                        hashtag=hashtag,
                        lastid=sentiments["lastid"],
                        chartdata=json.dumps(sentiments["chartdata"]),
                        labels=",".join(sentiments["labels"])))
    return resp


@app.route("/")
def index():
    form = ChooserForm()
    resp = make_response(render_template("index.html", form=form))
    return resp
    
