import sqlite3
import pandas as pd
import numpy as np
import time

from collections import Counter


def collapse_multiples(l, factor):
	'''
	Collapses `factor` duplicates of element in list into a single element.
	e.g. if l = [1,1,2,3,3,3,3] then collapse_multiples(l, 2) returns [1,2,3,3]
	
	INPUT:
		l: list
		factor: (int) collapse factor
	
	OUTPUT:
		collapsed list
	
	'''
	Counter(l)
	res = []
	for elem, n in Counter(l).items():
		if n % factor == 0:
			n /= factor
		res.extend([elem] * int(n))
	return res
	

def complete_tree_setup(df):
	"""
	`complete_tree`-specific helper. Sets up deep copy of df + dicts of
	video depths and recommendations for speedy lookup
	
	INPUT:
		pd.DataFrame of recommendations
	
	OUTPUT 
		res: (pd.DataFrame) deep copy of df with vertex_id column
		depths: (dict) dict of depths for videos in df
		recs: (dict) dict of recommendations for videos in df
	
	"""
	res = df.copy().filter(['video_id', 'recommendation', 'depth'])
	res['vertex_id'] = (res
						.groupby(['depth','video_id'])
						.ngroup())
	# video depths and recs as dicts for fast lookup
	depths = (df[['video_id', 'depth']]
				  .drop_duplicates()
				  .set_index('video_id')
				  .depth
				  .to_dict())
	recs = (df[['video_id', 'recommendation']]
			   .groupby('video_id')
			   .agg(lambda x: list(x))
			   .recommendation
			   .to_dict())
	return res, depth, recs

def list_difference(l1, l2):
	"""
	Returns l1 - l2
	e.g. list_difference([1,2,2,3,3,4], [2,2,3]) = [1,3,4]
	
	"""
	return [i for i in l1 if not i in l2 or l2.remove(i)]

def sample_list(l, p):
	"""
	Returns elements independently with probability p
	
	INPUT:
		l: list to sample
		p: probability of keeping each element
	
	OUTPUT:
		sampled list
	"""
	inds = np.random.rand(len(l)) < 1/p
	return list(np.array(l)[inds])
	

def complete_tree(df, search_id, n_splits=4, const_depth=5):
	"""
	Function which fills in a truncated tree.
	
	INPUT:
		df: pd.DataFrame with out-edges (columns=['video_id', 'depth', 'recommendation'])
		search_id: (int) id of the tree to populate
		n_splits: (int) splitting factor
		const_depth: (int) depth at which out-edges are sampled w.p. 1/n_splits
	
	OUTPUT:
		(pd.DataFrame) full tree
	
	"""
	res, vid_depths, vid_recs = complete_tree_setup(df)
	# get starting vertex index for new additions
	v_id = max(res.vertex_id.values)
	prev_recs = []
	for depth in df.depth.unique():
		parent_ids = list((res
					 .query('depth == @depth')
					 .video_id
					 .unique()))
		# get the recommendations that were not followed at the next level
		truncd_ids = list_difference(prev_recs, parent_ids)
		for video_id in truncd_ids:
			v_id += 1
			# skip if None or we don't have recommendations 
			if video_id is None or video_id not in vid_recs:
				continue
		
			recs = vid_recs[video_id]
			source_depth = vid_depths[video_id]
			if depth >= const_depth:
				n_followed.append(len(recs))
			
			# sample if we  are sampling, but our source recommendations were not sampled
			if depth >= const_depth and source_depth < const_depth:
				recs = sample_list(recs, p=1/len(recs))
			
			to_append = pd.DataFrame([[video_id, depth, v_id, rec] for rec in recs],
									columns=['video_id','depth','vertex_id','recommendation'])
			res = res.append(to_append)
		
		# update previous recs 
		prev_recs = list(res
			.query('depth == @depth')
			.recommendation
			.values)

	res = res.assign(search_id=search_id).sort_values(['depth', 'video_id'])
	return res



if __name__ == "__main__":
	con = sqlite3.connect('../../data/crawl.sqlite')
	cur = con.cursor()

	sql = '''
	SELECT r.* FROM recommendations r
	LEFT JOIN searches s
	  ON r.search_id=s.search_id
	WHERE s.date = '2019-08-31'
		AND video_id NOT NULL
	'''

	recs = pd.read_sql_query(sql, con)
	for search_id in recs.search_id.unique():
		df = recs.query("search_id == @search_id")

		# get search parameters
		sql = '''
		SELECT * FROM searches
		WHERE search_id = ?
		'''
		_, _, n_splits, _, _, _, const_depth = cur.execute(sql, (search_id,)).fetchone()

		# complete the tree and add to database
		res = complete_tree(df, search_id, n_splits=4, const_depth=5)
		pd.to_sql('recommendations_full', con, if_exists='append')

	con.commit()
	con.close()


