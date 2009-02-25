#!/bin/bash
#/Applications/VLC.app/Contents/MacOS/VLC -vvv "$1.mpg" :sout="#transcode{vcodec=mp4v,vb=1024,scale=1, \
#acodec=mp4a,ab=128,channels=2}:standard{access=file, \
#url=$1.mp4}" vlc:quit \
#--aspect-ratio "4:3" --sout-transcode-width 360 \
#--sout-transcode-height 240 --sout-transcode-fps 30 


/Applications/VLC.app/Contents/MacOS/VLC -I dummy -vvv "$1" :sout="#transcode{acodec=s16l,channels=2,ab=128}:standard{access=file,mux=wav,url=_$1.wav}" vlc://quit
