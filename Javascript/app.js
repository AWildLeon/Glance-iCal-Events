async function getAccessToken(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN) {
    const tokenUrl = "https://oauth2.googleapis.com/token";
    const data = new URLSearchParams();
    data.append("client_id", CLIENT_ID);
    data.append("client_secret", CLIENT_SECRET);
    data.append("refresh_token", REFRESH_TOKEN);
    data.append("grant_type", "refresh_token");
  
    const requestOptions = {
      method: "POST",
      body: data,
    };
  
    const response = await fetch(tokenUrl, requestOptions);
    if (response.ok) {
      const responseData = await response.json();
      return responseData.access_token;
    } else {
      return null;
    }
  }
  
  async function getCalendarEvents(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN) {
    const accessToken = await getAccessToken(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN);
    if (!accessToken) {
      return [];
    }
  
    const calendarUrl = "https://www.googleapis.com/calendar/v3/calendars/primary/events";
    const headers = {
      "Authorization": `Bearer ${accessToken}`,
    };
  
    const currentTime = new Date().toISOString();
    const timeMax = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(); // 30 days from now
  
    const urlParams = new URLSearchParams({
      timeMin: currentTime,
      timeMax: timeMax,
      singleEvents: "true",
      orderBy: "startTime",
    });
  
    const response = await fetch(`${calendarUrl}?${urlParams}`, { headers });
  
    if (response.ok) {
      const responseData = await response.json();
      return responseData.items || [];
    } else {
      return [];
    }
  }
  
  export default {
    async fetch(request, env, ctx) {
      const CLIENT_ID = await env.GoogleApiKeys.get('GoogleCalendarClientId');
      const CLIENT_SECRET = await env.GoogleApiKeys.get('GoogleCalendarClientSecret');
      const REFRESH_TOKEN = await env.GoogleApiKeys.get('GoogleCalendarRefreshToken');
      const events = await getCalendarEvents(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN);
      return new Response(JSON.stringify({ events }), {
        headers: { "Content-Type": "application/json" },
      });
    },
  };
  