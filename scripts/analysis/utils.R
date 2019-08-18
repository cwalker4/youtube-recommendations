# deal with python-formatted lists
format_python_lists <- function(rec_str) {
  if (rec_str == "[]" | is.na(rec_str)) {
    return(NA)
  }
  rec_str <- str_replace_all(rec_str, "[\\[\\]\\s']", '')
  return(strsplit(rec_str, ','))
}
