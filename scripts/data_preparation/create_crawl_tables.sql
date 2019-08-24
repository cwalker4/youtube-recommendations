-- main search information table
DROP TABLE IF EXISTS searches;
CREATE TABLE searches (
  search_id integer PRIMARY KEY,
  root_video text NOT NULL,
  n_splits integer NOT NULL,
  depth integer NOT NULL,
  date text NOT NULL,
  sample text NOT NULL,
  const_depth integer NOT NULL
);

-- video info table
DROP TABLE IF EXISTS videos;
CREATE TABLE videos (
  video_id text NOT NULL,
  search_id integer NOT NULL,
  title text,
  channel_id text,
  postdate text,
  views integer,
  likes integer,
  dislikes integer,
  n_comments integer,
  description text,
  category integer,
  PRIMARY KEY (video_id, search_id),
  FOREIGN KEY (search_id)
    REFERENCES searches (search_id)
);

-- channels table
DROP TABLE IF EXISTS channels;
CREATE TABLE channels (
  channel_id text NOT NULL,
  search_id integer NOT NULL,
  name text,
  country text,
  date_created text,
  n_subscribers integer,
  n_videos integer,
  n_views integer,
  PRIMARY KEY (channel_id, search_id),
  FOREIGN KEY (search_id)
    REFERENCES searches (search_id)
);

-- channel categories table
DROP TABLE IF EXISTS channel_categories;
CREATE TABLE channel_categories (
  channel_id text NOT NULL,
  search_id integer NOT NULL,
  category text,
  FOREIGN KEY (channel_id)
    REFERENCES channels (channel_id),
  FOREIGN KEY (search_id)
    REFERENCES searches (search_id)
);

-- recommendations table
DROP TABLE IF EXISTS recommendations;
CREATE TABLE recommendations (
  video_id text NOT NULL,
  search_id integer NOT NULL,
  recommendation text,
  depth integer,
  FOREIGN KEY (video_id, recommendation)
    REFERENCES videos (video_id, video_id),
  FOREIGN KEY (search_id)
    REFERENCES searches (search_id)
);
