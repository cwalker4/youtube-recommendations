library(dplyr)
library(readr)
library(here)
library(fuzzyjoin)
library(RSQLite)

###############################################################################
# Data import + standardizing
###############################################################################

media_indir <- 'data/media_outlets'

readr::read_csv(here::here(media_indir, 'adfontes_raw.csv')) %>%
  mutate(leaning_adfontes = case_when(`Horizontal Rank` < 0 ~ 'L',
                             `Horizontal Rank` > 0 ~ 'R',
                             `Horizontal Rank` == 0 ~ 'C')) %>%
  select(channel_name = `News Source`, leaning_adfontes) %>%
  mutate_at("channel_name", tolower) -> adfontes

readr::read_csv(here::here(media_indir, 'allsides_raw.csv')) %>%
  mutate(leaning_allsides = case_when(leaning %in% c("left-center", "left") ~ 'L',
                                      leaning %in% c("right-center", "right") ~ 'R',
                                      leaning %in% c("center") ~ 'C')) %>%
  filter(!is.na(leaning_allsides)) %>%
  select(channel_name = name, leaning_allsides) %>%
  mutate(channel_name = tolower(stringr::str_replace_all(channel_name, '-', ' '))) -> allsides

readr::read_csv(here::here(media_indir, 'mbfc_raw.csv')) %>%
  select(channel_name = name, leaning_mbfc = leaning) %>%
  mutate(leaning_mbfc = forcats::fct_collapse(as.factor(leaning_mbfc),
                                         L = c("extremeleft", "left", "leftcenter"),
                                         R = c("extremeright", "right", "rightcenter"),
                                         C = "center",
                                         group_other = TRUE)) %>%
  filter(leaning_mbfc != "Other") %>%
  mutate_at("channel_name", tolower) %>%
  mutate(leaning_mbfc = as.character(leaning_mbfc)) -> mbfc

###############################################################################
# Match scraped channels to leanings
###############################################################################

sql <- "
SELECT DISTINCT channel_id, LOWER(name) AS channel_name
FROM channels
"
con = dbConnect(SQLite(), here('data/crawl.sqlite'))
channels <- dbGetQuery(con, sql)

# join all our sources together with exact string matches
list(channels, adfontes, mbfc, allsides) %>%
  purrr::reduce(~ left_join(.x, .y, by = 'channel_name')) -> channels_matched

# take a majority vote of the three sources
channels_matched %>%
  select(-channel_id) %>%
  tidyr::gather(classifier, leaning, -channel_name) %>%
  filter(!is.na(leaning)) %>%
  count(channel_name, leaning) %>%
  group_by(channel_name) %>%
  summarise(leaning = leaning[which.max(n)]) -> channels_matched

# try a stringdist join on the unmatched channels
channels %>%
  filter(!channel_name %in% channels_matched$channel_name) -> channels_unmatched

list(mbfc, adfontes, allsides) %>%
  purrr::reduce(~ full_join(.x, .y, by = 'channel_name')) %>%
  tidyr::gather(source, leaning, -channel_name) %>%
  mutate(source = stringr::str_remove_all(source, "leaning_")) %>%
  filter(!channel_name %in% channels_matched$channel_name) -> classifications_unmatched

# fuzzy match and take majority vote
channels_unmatched %>%
  stringdist_left_join(classifications_unmatched, by = 'channel_name') %>%
  filter(!is.na(leaning)) %>%
  rename(channel_name = channel_name.x) %>%
  count(channel_name, leaning) %>%
  group_by(channel_name) %>%
  summarise(leaning = leaning[which.max(n)]) -> channels_approxmatched

# update channels_matched
channels_matched %>%
  bind_rows(channels_approxmatched) -> channels_matched

# update channels_unmatched and join in video counts
channels_unmatched %>%
  filter(!channel_name %in% channels_matched$channel_name) %>%
  left_join(channels, by = 'channel_name') -> channels_unmatched

###############################################################################
# Manual channel matching
###############################################################################

# fill in some manual matchings (mainly late night TV shows)
left_patterns <- c("the late show with stephen colbert", "lastweektonight", "saturday night live",
                   "real time with bill maher", "the daily show with trevor noah", "late night with seth meyers",
                   "al jazeera english", "the tonight show starring jimmy fallon", "the view", "jimmy kimmel live",
                   "60 minutes australia", "breakfast club power 105.1 fm", "cbs this morning", "cbs sunday morning",
                   "cnbc international tv", "cnbc television", "the new york times", "crooked media")

center_patterns <- c("tedx talks", "theellenshow", "bloomberg markets and finance", "bbc news", "bbc america",
                     "cnn business", "bloomberg politics")

right_patterns <- c("the hannity", "fox business", "fox 10 phoenix", "yaftv",
                    "fox news insider", "american conservative union", "dinesh d'souza", "fox news shows",
                    "jordan b peterson", "sean hannity", "glenn beck", "ben shapiro", "ben shapiro thug life",
                    "social justice fails")

tibble(channel_name = left_patterns, 
       leaning = rep_len('L', length(left_patterns))) -> left_tbl

tibble(channel_name = center_patterns) %>%
  mutate(leaning = 'C') -> center_tbl

tibble(channel_name = right_patterns) %>%
  mutate(leaning = 'R') -> right_tbl

bind_rows(left_tbl, center_tbl, right_tbl) %>%
  filter(!channel_name %in% channels_matched$channel_name) %>%
  distinct(channel_name, leaning) -> manual_matches

bind_rows(channels_matched, manual_matches) %>%
  left_join(channels, by = "channel_name") %>%
  filter(!is.na(channel_id)) %>%
  select(channel_id, leaning) -> channels_matched_full

# write new results to the database
dbWriteTable(con, "channel_leanings", channels_matched_full, overwrite = TRUE)


