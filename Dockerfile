
FROM ubuntu:disco

EXPOSE 8002

# Update to latest OS packages first
RUN apt-get update && \
    apt-get upgrade --no-install-recommends -y -o Dpkg::Options::="--force-confold" && \
    apt install -y --no-install-recommends nginx nginx-core \
        iproute2 python3.7 python3-pip python3-setuptools uwsgi \
	uwsgi-plugin-python3

COPY start.sh /app/start.sh

# Install flask, uwsgi, nginx, nltk, add our user and set up dir hierarchy
RUN /usr/bin/pip3 install flask nltk twython wtforms && \
    useradd -c "application user" -d /app --create-home -s /bin/bash appuser && \
    mkdir -p /app/au-pol-sentiment/static/c3 /app/au-pol-sentiment/static/d3 \
        /app/au-pol-sentiment/templates /app/htdocs /app/nltk_data && \
    rm /etc/nginx/sites-*/default && chmod a+rx /app/start.sh && \
    chown appuser /app/nltk_data && ln -s /app/nltk_data /usr/local/lib/nltk_data

    
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

USER appuser
WORKDIR /app

# Grab the NLTK data
RUN python3.7 -c "from nltk import download; download('twitter_samples');download('stopwords')"


COPY __init__.py creds.conf favicon.ico LICENSE README.md /app/au-pol-sentiment/
COPY templates/* /app/au-pol-sentiment/templates/

# We are we copying this in (and storing them in our github repo)
# rather than loading from cdnjs? CORS!
COPY static/c3/c3.js static/c3/c3.css /app/au-pol-sentiment/static/c3/
COPY static/d3/d3.js /app/au-pol-sentiment/static/d3/
COPY static/style.css /app/au-pol-sentiment/static
COPY nginx.conf /etc/nginx/sites-enabled/au-pol-sentiment
COPY wsgi.yaml /etc/uwsgi/apps-enabled

CMD /app/start.sh && sleep infinity
 