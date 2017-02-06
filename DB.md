###Agency Config

Agency config data is stored in MongoDB bravo.agencies collection.
Each document follows format:

```
{
    "name" : "AGENCY_SHORT_NAME",
    "alice" : {
        "name" : "BOT_NAME"
    },
    "config" : {
        "non_participant_days" : "<INT>"
        }
    },
    "cal_ids" : {
	"KEY_NAME_1" : "CALENDAR_ID@group.calendar.google.com",
	"KEY_NAME_2" : "CALENDAR_ID@group.calendar.google.com"
    },
    "emergency_contact" : {
        "name" : "NAME",
        "phone" : "INTERNATIONAL_FORMAT",
        "email" : "EMAIL"
    },
    "etapestry" : {
        "endpoint" : "ENDPOINT_URL",
        "pw" : "PASSWORD",
        "agency" : "AGENCY_NAME",
        "gifts" : {
            "fund" : "FUND",
            "approach" : "APPROACH",
            "campaign" : "CAMPAIGN"
        },
        "query_category" : "CATEGORY",
        "user" : "USER"
    },
    "google" : {
        "ss_id" : "BRAVO_SS_ID",
        "stats_ss_id" : "STATS_SS_ID",
        "geocode" : {
            "api_key" : "SERVICE_ACCT_API_KEY",
        },
        "oauth" : {
            "type" : "service_account",
            "project_id" : "SERV_ACCT_PROJ_ID",
            "private_key_id" : "PRIV_KEY_ID",
            "private_key" : "PRIV_KEY",
            "client_email" : "CLIENT_EMAIL",
            "client_id" : "CLIENT_ID",
            "auth_uri" : "AUTH_URI",
            "token_uri" : "TOKEN_URI",
            "auth_provider_x509_cert_url" : "CERT_URL",
            "client_x509_cert_url" : "CERT_URL"
        }
    },
    "mailgun" : {
        "from" : "EMAIL_ADDRESS",
        "domain" : "DOMAIN",
        "api_key" : "MAILGUN_API_KEY",
        "sandbox_to" : "EMAIL_ADDRESS"
    },
    "maps_id" : ObjectId("MONGODB_MAPS_ID"),
    "notify" : {
        "voice" : {
            "max_attempts" : "<INT>",
            "redial_delay" : "<INT>"
        }
    },
    "routing" : {
        "locations" : {
            "office" : {
                "name" : "NAME",
                "formatted_address" : "ADDRESS",
                "url" : "GOOGLE_MAPS_PLACE_URL"
            },
            "depots" : [ 
                {
                    "name" : "NAME",
                    "formatted_address" : "ADDRESS",
                    "blocks" : []
                }
            ]
        },
        "drivers" : [ 
            {
                "name" : "NAME",
                "shift_start" : "HR:MIN"
            }, 
            {
                "name" : "Default",
                "shift_start" : "HR:MIN"
            }
        ],
        "gdrive" : {
            "template_sheet_id" : "ROUTE_TEMPLATE_SS_ID",
            "routed_folder_id" : "ROUTED_FOLDER_ID",
            "permissions" : [ 
                {
                    "email" : "EMAIL",
                    "role" : "owner"
                }
            ]
        },
        "routific" : {
            "api_key" : "ROUTIFIC_API_KEY"
        },
        "traffic" : "API_CONF_VALUE",
        "min_per_stop" : "<INT>",
        "shift_end" : "HR:MIN",
        "view_days_in_advance" : "<INT>"
    },
    "scheduler" : {
        "notify" : {
            "cal_ids" : {
                "KEY_NAME_1" : "CALENDAR_ID@group.calendar.google.com",
                "KEY_NAME_2" : "CALENDAR_ID@group.calendar.google.com"
            },
            "preschedule_by_days" : "<INT>",
            "triggers" : {
                "email" : {
                    "enabled" : true,
                    "enabled_on" : "always",
                    "type" : "email",
                    "fire_days_delta" : "<NEGATIVE_INT>",
                    "fire_hour" : "<INT>",
                    "fire_min" : "<INT>"
                },
                "voice_sms" : {
                    "enabled" : true,
                    "enabled_on" : "no_mobile",
                    "type" : "voice",
                    "fire_days_delta" : "<NEGATIVE_INT>",
                    "fire_hour" : "<INT>",
                    "fire_min" : "<INT>"
                }
            }
        }
    },
    "twilio" : {
        "voice" : {
            "number" : "INTERNATIONAL_FORMAT",
            "caller_id" : "DISPLAY_NAME"
        },
        "api" : {
            "app_sid" : "ALICE_SID_ID",
            "auth_id" : "AUTH_ID",
            "sid" : "SID_ID"
        },
        "sms" : {
            "webhook" : {
                "on_receive" : "ENDPOINT_URL"
            },
            "number" : "INTERNATIONAL_FORMAT",
            "sid" : "NUMBER_SID_ID"
        }
    }
}
```
