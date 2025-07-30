#!/usr/bin/env python3

import io
import email
from glob import glob
import poplib
import time
import re
import configparser

POSTS = "/Users/dmd/Dropbox/dashare/zoolog/posts"

config = configparser.ConfigParser()
config.read('zoomail.ini')
USER = config['email']['USER']
PASS = config['email']['PASS']
SERVER = config['email']['SERVER']

pop = poplib.POP3(SERVER)
pop.user(USER)
pop.pass_(PASS)
resp, items, octets = pop.list()
print("connected ok to zoomail server")

for item in items:
    mid = int(item.split()[0])
    resp, text, octets = pop.retr(mid)
    text = b"\n".join(text)
    msg = email.message_from_string(text.decode("utf-8"))

    if type(msg.get_payload()) is list:
        # multipart message; get the plain version
        for part in msg.get_payload():
            if part.get_content_type() == "text/plain":
                plainbody = part.get_payload()
    else:
        plainbody = msg.get_payload()

    # get rid of the reply line
    cleanedbody = "\n".join(
        [
            line
            for line in plainbody.split("\n")
            if "zooreport@" not in line and not line.startswith(">")
        ]
    ).rstrip() + "\n"

    subject = msg.get("Subject").replace("Re: ", "")
    stripsubject = re.sub("[^0-9a-zA-Z]+", "-", subject)
    headerdate = time.strftime("%Y-%m-%d", email.utils.parsedate(msg["Date"]))

    output = "\n".join(("# " + subject.replace("Re: ", ""), "", cleanedbody))

    filename = POSTS + "/" + stripsubject + "-" + headerdate + ".txt"
    print("writing " + filename)
    open(filename, "w").write(output)
    pop.dele(mid)
    print("deleted email " + str(mid))

pop.quit()
print("finished with zoomail server")
