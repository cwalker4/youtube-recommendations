import json
import re
import os
from datetime import date
import time
import sys

import pandas as pd
import numpy as np
import networkx as nx

import sqlite3

# connect to the database
db_path = '../../data/crawl.sqlite'
conn = sqlite3.connect(db_path)

outdir = '../../data/derived_data/'

# get video_info
print("Getting video info...")
sql = "SELECT * FROM recommendations"
recs_df = pd.read_sql_query(sql, conn)

# aggregate all the out-edges for each video, drop videos that have no out-edges
edges = (recs_df[['video_id', 'recommendation']]
       .dropna()
       .groupby('video_id')
       .agg(lambda x: list(x))
       .query('recommendation != 0')
       .reset_index())

print("Building video adjacency...")
# write as a text file
f = open(os.path.join(outdir, 'video_adjacency.txt'), 'w')
for parent, children in zip(edges.video_id.values, edges.recommendation.values):
    if not children:
        continue
    line = '{} {}'.format(parent, " ".join(children))
    f.write(line + "\n")
f.close()

print("Building channel adjacency...")
# channel adjacency
sql = '''
SELECT v1.channel_id AS parent_channel, v2.channel_id as child_channel
FROM recommendations r
LEFT JOIN videos v1
  ON r.video_id = v1.video_id
LEFT JOIN videos v2
  ON r.recommendation = v2.video_id
'''

channel_recs = pd.read_sql_query(sql, conn)

edges = (channel_recs
        .dropna()
        .groupby('parent_channel')
        .agg(lambda x: list(x))
        .reset_index())

f = open(os.path.join(outdir, 'channel_adjacency.txt'), 'w')
for parent, children in zip(edges.parent_channel.values, edges.child_channel.values):
    if not children:
        continue
    line = '{} {}'.format(parent, " ".join(children))
    f.write(line + "\n")
f.close()

print("Getting video pageranks...")
# import the graph from adjacency list
G = nx.read_adjlist(create_using=nx.DiGraph(), 
                    path=os.path.join(outdir, "video_adjacency.txt"))

# load pageranks into a dataframe
pr = nx.pagerank(G)
pr_df = pd.DataFrame.from_dict(pr, orient="index").reset_index()\
                 .rename(index=str, columns={'index': 'video_id', 0: 'pagerank'})
    
pr_df.to_csv(os.path.join(outdir, 'video_pageranks.csv'), index=False)
