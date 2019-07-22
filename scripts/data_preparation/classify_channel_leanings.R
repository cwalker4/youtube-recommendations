library(dplyr)
library(readr)
library(here)
library(fuzzyjoin)

###############################################################################
# Data import + standardizing
###############################################################################

media_indir <- 'data/media_outlets'

readr::read_csv(here::here(media_indir, 'adfontes_raw.csv')) %>%
  mutate(leaning_adfontes = case_when(`Horizontal Rank` < 0 ~ 'L',
                             `Horizontal Rank` > 0 ~ 'R',
                             `Horizontal Rank` == 0 ~ 'C')) %>%
  select(channel = `News Source`, leaning_adfontes) %>%
  mutate_at("channel", tolower) -> adfontes

readr::read_csv(here::here(media_indir, 'allsides_raw.csv')) %>%
  mutate(leaning_allsides = case_when(leaning %in% c("left-center", "left") ~ 'L',
                                      leaning %in% c("right-center", "right") ~ 'R',
                                      leaning %in% c("center") ~ 'C')) %>%
  filter(!is.na(leaning_allsides)) %>%
  select(channel = name, leaning_allsides) %>%
  mutate(channel = tolower(stringr::str_replace_all(channel, '-', ' '))) -> allsides

readr::read_csv(here::here(media_indir, 'mbfc_raw.csv')) %>%
  select(channel = name, leaning_mbfc = leaning) %>%
  mutate(leaning_mbfc = forcats::fct_collapse(as.factor(leaning_mbfc),
                                         L = c("extremeleft", "left", "leftcenter"),
                                         R = c("extremeright", "right", "rightcenter"),
                                         C = "center",
                                         group_other = TRUE)) %>%
  filter(leaning_mbfc != "Other") %>%
  mutate_at("channel", tolower) %>%
  mutate(leaning_mbfc = as.character(leaning_mbfc)) -> mbfc

###############################################################################
# Match scraped channels to leanings
###############################################################################

video_indir <- 'data/derived_data/analysis_redo'

readr::read_csv(here::here(video_indir, 'video_info.csv')) %>%
  filter(!is.na(channel)) %>%
  count(channel) %>%
  arrange(-n) %>%
  mutate(channel = tolower(channel)) -> video_channels

# join all our sources together with exact string matches
list(video_channels %>% select(-n), adfontes, mbfc, allsides) %>%
  purrr::reduce(~ left_join(.x, .y, by = 'channel')) -> channels_matched

# take a majority vote of the three sources
channels_matched %>%
  tidyr::gather(classifier, leaning, -channel) %>%
  filter(!is.na(leaning)) %>%
  count(channel, leaning) %>%
  group_by(channel) %>%
  summarise(leaning = leaning[which.max(n)]) -> channels_matched

# try a stringdist join on the unmatched channels
video_channels %>%
  filter(!channel %in% channels_matched$channel) %>%
  select(-n) -> channels_unmatched

list(mbfc, adfontes, allsides) %>%
  purrr::reduce(~ full_join(.x, .y, by = 'channel')) %>%
  tidyr::gather(source, leaning, -channel) %>%
  mutate(source = stringr::str_remove_all(source, "leaning_")) %>%
  filter(!channel %in% channels_matched$channel) -> classifications_unmatched

# fuzzy match and take majority vote
channels_unmatched %>%
  stringdist_left_join(classifications_unmatched, by = 'channel') %>%
  filter(!is.na(leaning)) %>%
  rename(channel = channel.x) %>%
  count(channel, leaning) %>%
  group_by(channel) %>%
  summarise(leaning = leaning[which.max(n)]) -> channels_approxmatched

# update channels_matched
channels_matched %>%
  bind_rows(channels_approxmatched) -> channels_matched

# update channels_unmatched and join in video counts
channels_unmatched %>%
  filter(!channel %in% channels_matched$channel) %>%
  left_join(video_channels, by = 'channel') -> channels_unmatched

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

right_patterns <- c("the hannity", "fox business", "fox 10 phoenix", "yaftv", "fox business",
                    "fox news insider", "american conservative union", "dinesh d'souza", "fox news shows",
                    "jordan b peterson", "sean hannity", "glenn beck", "ben shapiro", "ben shapiro thug life",
                    "social justice fails")

tibble(channel = left_patterns, 
       leaning = rep_len('L', length(left_patterns))) -> left_tbl

tibble(channel = center_patterns) %>%
  mutate(leaning = 'C') -> center_tbl

tibble(channel = right_patterns) %>%
  mutate(leaning = 'R') -> right_tbl

bind_rows(channels_matched, left_tbl, center_tbl, right_tbl) -> channels_matched

channels_matched %>%
  write_csv(here::here('data/derived_data/analysis_redo/channel_classification.csv'))


