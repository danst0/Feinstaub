#!/bin/bash

WDIR=/home/pi

stty -F /dev/ttyUSB0 9600 raw

INPUT=$(od --endian=big -x -N10 < /dev/ttyUSB0|head -n 1|cut -f2-10 -d" ");

#Ausgabe
echo $INPUT
echo " "

FIRST4BYTES=$(echo $INPUT|cut -b1-4);
echo $FIRST4BYTES

if [ "$FIRST4BYTES" = "aac0" ]; then
  echo "check for correct intro characters: ok"
  # logger "check for correct intro characters: ok"
else
  echo "incorrect sequence, exiting"
  #logger "incorrect sequence, exiting"
  exit;
fi

PPM25LOW=$(echo $INPUT|cut -f2 -d " "|cut -b1-2);
PPM25HIGH=$(echo $INPUT|cut -f2 -d " "|cut -b3-4);

PPM10LOW=$(echo $INPUT|cut -f3 -d " "|cut -b1-2);
PPM10HIGH=$(echo $INPUT|cut -f3 -d " "|cut -b3-4);

#zu Dezimal konvertieren
PPM25LOWDEC=$( echo $((0x$PPM25LOW)) );
PPM25HIGHDEC=$( echo $((0x$PPM25HIGH)) );

PPM10LOWDEC=$( echo $((0x$PPM10LOW)) );
PPM10HIGHDEC=$( echo $((0x$PPM10HIGH)) );

PPM25=$(echo "scale=1;((( $PPM25HIGHDEC * 256 ) + $PPM25LOWDEC ) / 10 ) "|bc -l );
PPM10=$(echo "scale=1;((( $PPM10HIGHDEC * 256 ) + $PPM10LOWDEC ) / 10 ) "|bc -l );

#logger "Feinstaub PPM25: $PPM25"
#logger "Feinstaub PPM10: $PPM10"

echo "Feinstaub PPM25: $PPM25"
echo "Feinstaub PPM10: $PPM10"

#echo $PPM25 > $WDIR/etc/ppm25.txt
#echo $PPM10 > $WDIR/etc/ppm10.txt

echo "Upload der Daten zu Sparkfun. Public Key: 1n4x2aapnqIpXp2zZzwo"
wget -qO- "http://data.sparkfun.com/input/1n4x2aapnqIpXp2zZzwo?private_key=0mbx4yyBmZFjYjVk8kqB&pm10=$PPM10&pm25=$PPM25" &> /dev/null


if [ -f feinstaub.rrd ];
then
  echo "Round Robin eintragen"
  rrdtool update feinstaub.rrd N:$PPM10:$PPM25
  echo "Graph generieren"
  rrdtool graph fseinstaub.jpg --start -12h --title "Feinstaubmessung" --vertical-label "ug/m3" DEF:pm10=feinstaub.rrd:pm10:AVERAGE DEF:pm25=feinstaub.rrd:pm25:AVERAGE LINE1:pm10#ff0000:"PPM10" LINE2:pm25#00ff00:"PPM2.5"
else
  echo "Round Robin anlegen"
  rrdtool create feinstaub.rrd --step 60 DS:pm10:GAUGE:120:0:500 DS:pm25:GAUGE:120:0:500 RRA:AVERAGE:0.5:60:24 RRA:AVERAGE:0.5:288:31
fi

