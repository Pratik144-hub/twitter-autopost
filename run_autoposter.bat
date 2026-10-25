@echo off
title TweetyTweets Autoposter
echo ==============================================
echo  TweetyTweets Autonomous Posting Loop
echo ==============================================
echo Make sure your browser session (launch_browser.bat) is running!
echo This window will monitor your schedule and publish posts when due.
echo.
python scripts\autopost_loop.py
pause
