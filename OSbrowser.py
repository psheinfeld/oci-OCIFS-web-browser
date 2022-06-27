from asyncio import subprocess
from concurrent.futures import thread
from distutils.log import debug
from sys import prefix
from unicodedata import name
from flask import Flask
from flask import render_template_string
from flask import request,Response
from flask import redirect
import oci
import requests


#init OS client
signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
object_storage_client = oci.object_storage.ObjectStorageClient(config={},
                                                               signer=signer)

#get instanse compartment
instance_metadata = requests.get("http://169.254.169.254/opc/v2/instance/",
                                 headers={"Authorization": "Bearer Oracle"})
instance_compartmentId = (instance_metadata.json())['compartmentId']

#get namespace
namespace = object_storage_client.get_namespace().data

#get buckets
buckets = [
    bck.name for bck in object_storage_client.list_buckets(
        namespace, instance_compartmentId).data
]

#flask
app = Flask(__name__)

def level_up(path_in_bucket):
    loc = path_in_bucket.rfind('/',0,-2) if path_in_bucket.count('/')>1 else -1
    return path_in_bucket[0:loc+1] if loc > 0 else ''


def items_at_path(bucket=None, prefix=''):
    if not bucket:
        return []
    items = (object_storage_client.list_objects(namespace,
                                                bucket,
                                                prefix=prefix)).data
    items = [item.name  for item in items.objects]
    objects = {}
    for obj_name in items:
        obj = obj_name.replace(prefix,'')
        ll = obj.split('/')
        val = (ll[0] + '/') if len(ll) > 1 else ll[0]
        if not val == '':
            objects[val]=val
    
    return objects.keys()


@app.route('/')
def root():
    bucket = request.args.get('b')
    root_level = True if not bucket else False

    if not root_level and bucket not in buckets:
        return redirect('/')

    path_in_bucket = request.args.get('p')
    if not path_in_bucket:
        path_in_bucket = ''
    return render_template_string('''
    <html>
        <head>
        <title>Bucket viewer</title>
        <style>
        ul#menu li {
        display:inline;
        }
        body { font-family: helvetica; }
        </style>

        </head>
        <body>
        
        <div align = "center">

        {% if not root_level %}
            
            <ul id="menu">
            {% for bct in buckets %}
                {% if bct == current_bucket %}
                <li> <b><a href="/?b={{bct}}&p=">{{bct}}</a></b></li>
                {% else %}
                <li > <a href="/?b={{bct}}&p=">{{bct}}</a></li>
                {% endif %}

            {% endfor %}
            </ul>
            <h1>Bucket: {{current_bucket}}</h1>
        {% endif %}
        
        </div>
        {% if root_level %}
            <ul >
            {% for bct in buckets %}
                <li><a href="/?b={{bct}}">{{bct}}</a></li>
            {% endfor %}
            </ul>
        {% else %}
            <ul>
            {% if '/' in path_in_bucket %}
                <li ><a href="/?b={{current_bucket}}&p={{level_up}}">..</a></li>
            {% endif %}
            {% for object in objects_list %}
                {% if '/' in object %}
                <li ><a href="/?b={{current_bucket}}&p={{path_in_bucket}}{{object}}">{{object}}</a></li>
                {% else %}
                <li ><a href="/get/{{object}}?b={{current_bucket}}&o={{path_in_bucket}}{{object}}">{{object}}</a></li>
                {% endif %}
            {% endfor %}
            </ul>
        {% endif %}
        </body>
    </html>
    ''',
        buckets=buckets,
        current_bucket = bucket,
        path_in_bucket = path_in_bucket,
        level_up = level_up(path_in_bucket),
        objects_list=items_at_path(bucket, path_in_bucket),
        root_level=root_level)

@app.route('/get/<filename>')
def get(filename):
    object_name = request.args.get('o')
    bucket = request.args.get('b')
    print(object_name)

    resp = object_storage_client.get_object(namespace,bucket,object_name)
    excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
    headers = [(name, value) for (name, value) in resp.headers.items()
               if name.lower() not in excluded_headers]

    #Content-Disposition: attachment; filename=
    headers = headers +  [('Content-Disposition', 'attachment')]

    response = Response(resp.data, resp.status, headers)
    return response

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
