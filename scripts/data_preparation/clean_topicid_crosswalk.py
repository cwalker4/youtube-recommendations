lines = []
with open('../../data/derived_data/topicid_crosswalk.txt', 'r') as f:
	for line in f:
		cleaned = line.strip().split(maxsplit=1)
		lines.append(",".join(cleaned))

with open('../../data/derived_data/topicid_crosswalk.csv', 'w') as f:
	f.write('id,label\n')
	f.write('\n'.join(lines))
