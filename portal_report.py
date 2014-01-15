import csv
import json
import sys
import os
import socket
from calendar import timegm
from datetime import datetime, timedelta
import requests

option_show_traffic = False
option_get_usage_report = False
option_get_groups = True
option_get_items = True
option_get_credits = False  # not yet implemented
encoding = 'utf-8'


def main(argv=None):
    #socket.setdefaulttimeout(30) # in seconds
    portal_name = 'demo-es'
    username    = 'javier.abadia.demo'
    
    portal_name = raw_input("Portal name [%s]: " % portal_name) or portal_name
    portal_url = 'http://' + portal_name + '.maps.arcgis.com'
    username = raw_input("User name [%s]: " % username) or username
    password = raw_input("Password: ")

    if not os.path.exists(portal_name):
        os.makedirs(portal_name)
        
    os.chdir(portal_name)

    # Setup the URLs used to connect to portal
    rest_url = portal_url + '/sharing/rest'
    content_url = portal_url + '/sharing/content'
    secure_rest_url = rest_url.replace('http://', 'https://')

    # Generate a token (if username and password are provided)
    token = None
    if username and password:
        token = get_token(secure_rest_url, username, password)

    print "# PORTAL:  ", portal_url
    print "# USUARIO: ", username
    print "# TOKEN:   ",token

    # Retrieve the portal properties, and switch to using HTTPS only if
    # the portal is configured to all SSL
    portal_properties = get_portal_properties(secure_rest_url, token)
    if portal_properties.get('allSSL'):
        rest_url = secure_rest_url

    org_id = portal_properties.get('id')

    f = open("properties.json","w")
    f.write(json.dumps(portal_properties))
    f.close()

    if option_get_usage_report:
        print "Getting Usage Report"
        # Prepare the query that checks for things modified within the last week.
        # Also append the org's ID to restrict searches to within the organization.
        today = datetime.utcnow()
        weekago = today - timedelta(weeks=4)
        q = 'modified:[' + portal_time(weekago) + ' TO ' + portal_time(today) + ']'
        if org_id:
            q += ' accountid:' + org_id

        # Search the portal, making a call  for each "page" of results
        results, next_start = search(rest_url, q, 1, 100, token)
        while next_start > 0:
            page_results, next_start = search(rest_url, q, next_start, 100, token)
            results.extend(page_results)

        # Loop over the results and write them to a CSV file
        fields = ['id', 'title', 'owner', 'numViews']
        csvfile = csv.writer(open('usage_report.csv', 'wb'), delimiter=';')
        csvfile.writerow(fields)
        for item in results:
            row = [item[field] for field in fields]
            row = [(field.encode(encoding) if isinstance(field,unicode) else field) for field in row]
            csvfile.writerow(row)
            #print row

    if option_get_groups:
        print "Getting Groups"
        #get list of groups
        groups = get_groups(rest_url, org_id, token)
        #print json.dumps(groups,encoding)
        fields = ['id', 'owner', 'title', 'snippet','description','tags','thumbnail']
        csvfile = csv.writer(open('groups.csv', 'wb'), delimiter=';')
        csvfile.writerow(fields)
        for group in groups:
            group['tags'] = ','.join([tag.encode(encoding) for tag in group['tags']])
            row = [group[field] for field in fields]
            row = [(field.encode(encoding) if isinstance(field,unicode) else field) for field in row]
            csvfile.writerow(row)
            if group['thumbnail']:
                save_group_thumbnail(rest_url, group, token)
            print '.',

    if option_get_items:
        print "Getting Items"
        items = get_items(rest_url, org_id, token)
        fields = ['id', 'title', 'owner', 'type', 'numViews', 'snippet','description','tags','thumbnail','url','typeKeywords','modified','extent']
        csvfile = csv.writer(open('items.csv', 'wb'), delimiter=';')
        csvfile.writerow(fields)
        for item in items:
            item['modified'] = local_time(item['modified'])
            item['tags'] = ','.join([tag.encode(encoding) for tag in item['tags']])
            item['typeKeywords'] = ','.join([tag.encode(encoding) for tag in item['typeKeywords']])
            row = [item[field] for field in fields]
            row = [(field.encode(encoding) if isinstance(field,unicode) else field) for field in row]
            csvfile.writerow(row)
            if item['thumbnail']:
                save_item_thumbnail(content_url, item, token)

            if item['type'] == 'Web Map':
                save_webmap(content_url,item,token)
            #if item['type'] == 'CSV':
            #    print item.

            print '.',

    if option_get_credits:
        print "Getting Credit consumption"
        # not yet implemented
        print '.',
        

def get_token(rest_url, username, password):
    ip = socket.gethostbyname(socket.gethostname())
    referer = socket.gethostbyaddr(ip)[0]
    postdata = { 'username': username, 'password': password,\
                 'client': 'referer', 'referer': referer,\
                 'expiration': 60, 'f': 'json' }
    resp = send_post_request(rest_url + '/generateToken', postdata)
    return resp['token']

def get_portal_properties(rest_url, token):
    postdata = { 'f': 'json' }
    if token:
        postdata['token'] = token
    return send_post_request(rest_url + '/portals/self', postdata)

def get_groups(rest_url, org_id, token):
    groups = []
    postdata = { 'f': 'json', 'num' : 100, 'q': 'accountid:' + org_id }
    if token:
        postdata['token'] = token
    response = send_post_request(rest_url + '/community/groups', postdata)
    next_start = response['nextStart']
    groups.extend(response['results'])
    while next_start > 0:
        postdata['start'] = next_start
        response = send_post_request(rest_url + '/community/groups', postdata)
        next_start = response['nextStart']
        groups.extend(response['results'])
    return groups

def get_items(rest_url, org_id, token):
    items = []
    postdata = { 'f': 'json', 'num' : 100, 'q': 'accountid:' + org_id }
    if token:
        postdata['token'] = token
    response = send_post_request(rest_url + '/search', postdata)
    next_start = response['nextStart']
    items.extend(response['results'])
    while next_start > 0:
        postdata['start'] = next_start
        response = send_post_request(rest_url + '/search', postdata)
        next_start = response['nextStart']
        items.extend(response['results'])
    return items

def save_group_thumbnail(rest_url, group, token):
    postdata = {}
    postdata['token'] = token
    url = rest_url + '/community/groups/' + group['id'] + '/info/' + group['thumbnail']
    r = requests.post(url, data=postdata)
    img = r.content
    f = open('group_ ' + group['id'] + '_' + group['thumbnail'], "wb")
    f.write(img)
    f.close()

def save_item_thumbnail(content_url, item, token):
    postdata = {}
    postdata['token'] = token
    url = content_url + '/items/' + item['id'] + '/info/' + item['thumbnail']
    if option_show_traffic:
        print '=='
        print url
        print postdata
        print '-'            
    r = requests.post(url,data=postdata)    
    img = r.content
    filename,extension = os.path.splitext(item['thumbnail'])
    filename = 'item_' + item['id'] + '_thumbnail' + extension
    f = open(filename, "wb")
    f.write(img)
    f.close()

def save_webmap(content_url, item, token):
    postdata = { 'pretty' : 'true' }
    postdata['token'] = token
    url = content_url + '/items/' + item['id'] + '/data'
    if option_show_traffic:
        print '=='
        print url
        print postdata
        print '-'            
    r = requests.post(url, data=postdata)
    webmap = r.content
    f = open('item_' + item['id'] + '_webmap.json', "w")
    f.write(webmap)
    f.close()

def portal_time(dt):
    # Turns a UTC datetime object into portal's date/time string format.
    return '000000' + str(timegm(dt.timetuple()) * 1000)

def local_time(ts):
    return datetime.fromtimestamp(ts / 1000)

def search(rest_url, q, start, num, token):
    postdata = { 'q': q, 'start': start, 'num': num, 'f': 'json' }
    if token:
        postdata['token'] = token
    resp = send_post_request(rest_url + '/search', postdata)
    return resp['results'], resp['nextStart']

def send_post_request(url, postdata):
    r = requests.post(url, data=postdata)
    response = r.json()
    if option_show_traffic:
        print '=='
        print url
        print postdata
        print '-'    
        print response
    if 'error' in response:
        error_message = response['error']['message']
        print error_message
        for error_detail in response['error']['details']:
            print error_detail
        raise StandardError('Portal error: ' + error_message)
    return response

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
