const axios = require('axios');
const { EventSource } = require('eventsource');

const BASE = process.env.SCRAPER_BASE_URL || 'http://localhost:8001';
const retailer = process.env.TEST_RETAILER || 'asos.com';
const query = process.env.TEST_QUERY || 'white shirt';

(async function run() {
  try {
    const { data } = await axios.post(`${BASE}/scrape`, {
      query,
      retailer,
      headers: { 'User-Agent': 'Mozilla/5.0' }
    }, { timeout: 15000 });
    const jobId = data.job_id;
    console.log('job_id:', jobId);

    const es = new EventSource(`${BASE}/events/${jobId}`);
    let count = 0;
    const max = 20; // stop after a few items

    const timeout = setTimeout(() => {
      console.log('timeout: no more events in time window');
      es.close();
      process.exit(0);
    }, 60000);

    es.onmessage = (ev) => {
      console.log(ev.data);
      try {
        const payload = JSON.parse(ev.data);
        if (payload.type === 'item') {
          count++;
          if (count >= max) {
            clearTimeout(timeout);
            es.close();
            process.exit(0);
          }
        }
        if (payload.type === 'complete') {
          clearTimeout(timeout);
          es.close();
          process.exit(0);
        }
      } catch {}
    };

    es.onerror = (err) => {
      console.error('sse error:', err);
      clearTimeout(timeout);
      es.close();
      process.exit(1);
    };
  } catch (e) {
    console.error('request error:', e.message);
    process.exit(1);
  }
})();