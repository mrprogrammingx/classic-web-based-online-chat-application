/**
 * tests/js/rooms-search-debounce.test.js
 * Verify the rooms search input is debounced and page-size selection influences the fetch limit.
 */

describe('rooms search debounce and page-size', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    document.body.innerHTML = `
      <div id="rooms-list"></div>
      <input id="rooms-search" />
      <select id="rooms-page-size"><option value="10">10</option><option value="25">25</option><option value="50">50</option></select>
      <div id="rooms-pagination" data-offset="0"></div>
    `;
    window.SITE_CONFIG = window.SITE_CONFIG || {};
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
    jest.resetAllMocks && jest.resetAllMocks();
    delete window.SITE_CONFIG;
  });

  test('debounces input and uses page-size for limit', async () => {
    const roomsPayload = { rooms: [{ id: 1, name: 'R1', member_count: 1, is_member: false }], total: 100 };

    const fetchMock = jest.fn((url, opts) => {
      // return the same payload for any /rooms GET
      const u = String(url || '');
      if(u.indexOf('/rooms') !== -1){
        return Promise.resolve({ status: 200, json: () => Promise.resolve(roomsPayload) });
      }
      return Promise.resolve({ status: 404, json: () => Promise.resolve({}) });
    });
    global.fetch = fetchMock;

    window.showStatus = window.showStatus || function(){};
    window.showToast = window.showToast || function(){};
    window.authHeaders = window.authHeaders || function(){ return {}; };

    // Load rooms script and allow initial render
    require('../../static/app/lib/rooms.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    // let any pending promises settle
    await Promise.resolve();

    // clear initial fetch calls so we can measure debounced ones
    fetchMock.mockClear();

    const search = document.getElementById('rooms-search');
    // simulate fast typing: two input events in quick succession
    search.value = 'a';
    search.dispatchEvent(new Event('input'));
    search.value = 'ab';
    search.dispatchEvent(new Event('input'));

    // advance just short of debounce (250ms)
    jest.advanceTimersByTime(249);
    // allow microtasks
    await Promise.resolve();
    expect(fetchMock).toHaveBeenCalledTimes(0);

    // advance past debounce
    jest.advanceTimersByTime(2);
    await Promise.resolve();
    // now a single fetch should have happened for the debounced search
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Now test page-size change triggers immediate fetch with limit param
    fetchMock.mockClear();
    const pageSize = document.getElementById('rooms-page-size');
    pageSize.value = '25';
    pageSize.dispatchEvent(new Event('change'));
    await Promise.resolve();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const calledUrl = String(fetchMock.mock.calls[0][0] || '');
    expect(calledUrl).toMatch(/limit=25/);
  });

});
