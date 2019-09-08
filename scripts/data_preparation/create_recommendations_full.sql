DROP TABLE IF EXISTS recommendations_full;
CREATE TABLE recommendations_full (
  video_id text NOT NULL,
  vertex_id integer NOT NULL,
  search_id text NOT NULL,
  recommendation text,
  depth integer
);