#!/bin/bash
echo "Backing up database..."
ssh cwalker4@yen.stanford.edu 'sqlite3 ~/repositories/youtube-recommendations/data/crawl.sqlite ".backup /home/users/cwalker4/repositories/youtube-recommendations/data/crawl_backup.sqlite"'
echo "Copying database..."
rsync cwalker4@yen.stanford.edu:"~/repositories/youtube-recommendations/data/crawl_backup.sqlite" "data/crawl.sqlite"
echo "Done!"
