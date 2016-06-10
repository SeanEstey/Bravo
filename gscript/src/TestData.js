/* Data for use in Tests.gs */

/*
var TestConfig = {
  "etw_res_cal_id": "7d4fdfke5mllck8pclcerbqk50@group.calendar.google.com",
  "gdrive": {
    "ss_ids": {
      'bravo': '1JjibGqBivKpQt4HSW0RFfuTPYAI9LxJu-QOd6dWySDE',   // DEV_SS
      'stats': '1iBRJOkSH2LEJID0FEGcE3MHOoC5OKQsz0aH4AAPpTR4',
      'stats_archive': '1BTS-r3PZS3QVR4j5rfsm6Z4kBXoGQY8ur60uH-DKF3o',
      'inventory': '1Mb6qOvYVUF9mxyn3rRSoOik427VOrltGAy7LSIR9mnU',
      'route_template': '1Sr3aPhB277lESuOKgr2EJ_XHGPUhuhEEJOXfAoMnK5c'
    },
    'folder_ids': {
      'routed': '0BxWL2eIF0hwCRnV6YmtRLVBDc0E',
      'entered': '0BxWL2eIF0hwCOTNSSy1HcWRKUFk'
    },
  },
  "cal_ids": {
    'res': '7d4fdfke5mllck8pclcerbqk50@group.calendar.google.com',
    'bus': 'bsmoacn3nsn8lio6vk892tioes@group.calendar.google.com',
  },
  'depots' : {
    'abc': {
      'name': 'ABC',
      'location': '14142 140 St NW, Edmonton, AB',
      'blocks': ['B1A', 'B2A', 'B3A', 'B4A', 'B5A', 'B6A']
    },
    'univer' : {
      'name': 'Univer', 
      'location': '8221 127 Ave NW, Edmonton, AB',
      'blocks': ['R2C', 'R2M', 'R1A'], 
      'postal': ['T8N', 'T5E', 'T5A', 'T5C', 'T5L', 'T5Y', 'T5Z', 'T5X', 'T6V']
    },
    'strathcona': {
      'name': 'Strathcona',
      'location': '10347 73 Ave NW, Edmonton, AB',
      'blocks': ['B1D', 'B2D', 'B3D', 'B4D', 'B5D', 'B6D']
    },
    'fir street': {
      'name': 'Fir Street',
      'location': '979 Fir St, Sherwood Park, AB',
      'postal': ['T8A', 'T8H', 'T8L']
    }
  },
  'booking': {
    'max_block_radius': 10,
    'max_schedule_days_wait': 14,
    'search_weeks': 16,
    'size': {
      'res': {
        'medium': 60,
        'large': 75,
        'max': 90,
      },
      'bus': {
        'medium': 20,
        'large': 23,
        'max': 25
      }
    }
  }
};

//---------------------------------------------------------------------
var TestData = {
  // 12 weeks
  "res_cal_events": Schedule.getEventsBetween(
    TestConfig['etw_res_cal_id'], 
    new Date(Date.now() + (24 * 3600 * 1000)), 
    new Date(Date.now() + (1000 * 3600 * 24 *  7 * 12))
  ),
  "res_bus_cal_events": Schedule.getEventsBetween(
    TestConfig['etw_res_cal_id'], 
    new Date(), 
    new Date(Date.now() + (1000 * 3600 * 24 *  7 * 12)))
    .concat(Schedule.getEventsBetween(
      TestConfig['cal_ids']['bus'], 
      new Date(), 
      new Date(Date.now() + (1000 * 3600 * 24 *  7 * 12)))
  ),
  "route_id": "1nLxNgkkCtXftPzASc09RRO29bJGqU2PI3UGcnrsz0LY", // May 18: B6C (Rod) 
  "edmonton_address": "411 Heffernan Drive NW, Edmonton, AB",
  "pickup_dates": {
    "B4A": new Date("Oct 24, 2015"),
    "R5G": new Date("Dec 24, 2015"),
    "R7B": new Date("Sep 24, 2015")
  },
  "route_row": {
    'name_or_address': '1234 5 st',
    'gift': '5',
    'driver_input': 'nh', 
    'order_info': '_placeholder_',
    'account_num': 12345, 
    'driver_notes': 'dropoff today', 
    'blocks': 'B4A, R5G, R7B',
    'neighborhood': 'Oliver', 
    'status': 'Dropoff', 
    'office_notes': '***RMV R5G*** no tax receipt'
  },
  "map_data": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": {
          "type": "Polygon",
          "coordinates": [
            [
              [
                -113.5555673,
                53.502387,
                0
              ],
              [
                -113.5570264,
                53.501365899999996,
                0
              ],
              [
                -113.5565114,
                53.49748580000001,
                0
              ],
              [
                -113.5411048,
                53.4975113,
                0
              ],
              [
                -113.5411477,
                53.5044034,
                0
              ],
              [
                -113.5438943,
                53.5047097,
                0
              ],
              [
                -113.5461259,
                53.50302510000001,
                0
              ],
              [
                -113.5555673,
                53.502387,
                0
              ]
            ]
          ]
        },
        "properties": {
          "name": "R3E [Grandview Heights]",
          "description": "gx_image_links: ",
          "gx_image_links": ""
        }
      }
    ]
  }
};
*/