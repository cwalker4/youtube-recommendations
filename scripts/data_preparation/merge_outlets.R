library(dplyr)
library(tidyr)
library(here)
library(readr)
library(forcats)
library(stringr)

###############################################################################
# Data import + standardizing
###############################################################################

# A few steps here:
#   1. collapse leanings to L/C/R
#   2. make names lowercase and replace spaces with dashes

# MBFC
read_csv(here('data/media_outlets/mbfc_raw.csv')) %>%
  mutate(leaning_mbfc = fct_collapse(as.factor(leaning),
                                     L = c('left', 'leftcenter', 'extremeleft'),
                                     R = c('right', 'right-center', 'rightcenter', 'extremeright'),
                                     C = 'center')) %>%
  select(name, leaning_mbfc, url) -> mbfc

# Adfontes
readr::read_csv(here::here('data/media_outlets/adfontes_raw.csv')) %>%
  mutate(leaning_adfontes = case_when(`Horizontal Rank` < 0 ~ 'L',
                                      `Horizontal Rank` > 0 ~ 'R',
                                      `Horizontal Rank` == 0 ~ 'C')) %>%
  select(name = `News Source`, leaning_adfontes) %>%
  mutate_at("name", ~str_replace_all(tolower(.), ' ', '-')) -> adfontes

# Allsides
read_csv(here('data/media_outlets/allsides_raw.csv')) %>%
  filter(!grepl('^allsides', name),
         leaning != 'allsides') %>%
  mutate(leaning_allsides = fct_collapse(as.factor(leaning),
                                         L = c('left', 'left-center'),
                                         R = c('right', 'right-center'),
                                         C = 'center')) %>%
  mutate_at('name', ~str_replace_all(., '-media-bias|-[:digit:]', '')) %>% # drop weird trailers
  select(name, leaning_allsides) -> allsides

###############################################################################
# Merge sources
###############################################################################

# compile all the sources
list(select(mbfc, name, leaning), adfontes, allsides) %>%
  purrr::reduce(~full_join(.x, .y, by = 'name')) %>%
  mutate_all(as.character) %>%
  gather(source, leaning, -name, na.rm = TRUE) %>%
  mutate_at('source', ~str_replace(., '^leaning_', '')) -> leanings_full

# get a unique classification by taking a majority vote of the three sources
leanings_full %>%
  group_by(name) %>%
  summarise(leaning = leaning[which.max(n())]) -> leanings

# join back in the source URLs from MBFC
leanings %>%
  left_join(mbfc %>% select(name, url), by = 'name') -> leanings

###############################################################################
# TODO: Manual editing
###############################################################################

# There are a bunch of dupes that are hard to catch systematically (e.g. abc/abc-news, nyt/new-york-times).
# Getting rid of them will take manually scrubbing through the classifications.

###############################################################################
# Save 
###############################################################################

write_csv(leanings, here('data/media_outlets/outlet_leanings.csv'))


