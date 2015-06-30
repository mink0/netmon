This tool was created to provide network infrastructure monitoring. Snmp collector (a separate process via crontab) receives bandwidth data from configured net devices and stores it in a PostgreSQL database. Django is used as back end and provides REST API to this database. Also Django is used to generate its own snmp queries to provide a real time statistics (such as MAC tables, current interface bandwidth and etc.). All plots are highly interactive and are made using Flot (flotcharts.org) + JQuery. This app is currently used in production.

Copyright (c) 2011

![ScreenShot](https://raw.github.com/minkolazer/netmon/master/1-netmon_index.png)

![ScreenShot](https://raw.github.com/minkolazer/netmon/master/2-netmon_if_week.png)

![ScreenShot](https://raw.github.com/minkolazer/netmon/master/3-netmon_if_day.png)

![ScreenShot](https://raw.github.com/minkolazer/netmon/master/5-netmon_macs.png)


