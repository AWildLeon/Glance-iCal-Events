## Google Calendar List Extension for https://github.com/glanceapp/glance

You can use this extension to list Google Calendar events in your Glance dashboard.

![demo](./demo.png)

You can use the following options to run the app:
1. [Python](./Python) - Docker app

## To get started:

4. Configure and run service 
        2. Run <code>docker compose up --remove-orphans -d</code>
        3. This service will run on port 8075 unless configured otherwise.


5. Glance Configuration:  
```
- type: custom-api
    title: Upcoming Google Calendar Events
    cache: 1h
    url: ${GOOGLE_CALENDAR_SERVER}
    template: |
    <div>
        {{ range .JSON.Array "events" }}
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <div class="size-h3" style="text-align: left; width: 175px;">{{ .String "summary" }}</div>
        <div class="size-h4" style="text-align: left;">{{ .String "start.dateTime" | parseLocalTime "rfc3339" }}</div>
        <div class="color-primary size-h3" style="text-align: right; width: 75px;" {{ .String "start.dateTime" | parseTime "rfc3339" | toRelativeTime }}></div>
        </div>
    {{ end }}
    </div>
```
