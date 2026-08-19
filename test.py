import requests
import json


API_URL = (
    "https://jiotvapi.cdn.jio.com/"
    "apis/v3.0/getMobileChannelList/get/"
    "?langId=6&devicetype=phone&os=android"
    "&usertype=JIO&version=343"
)


BASE_LOGO_URL = (
    "https://jiotvimages.cdn.jio.com/dare_images/images/"
)


# ============================================================
# LANGUAGE ID MAP
# ============================================================
#
# These names are inferred from the channel names in the
# supplied channel data. The API itself returns IDs.
#
# ============================================================

LANGUAGE_MAP = {

    1: "Hindi",

    2: "English",

    3: "Punjabi",

    4: "Marathi",

    5: "Gujarati",

    6: "English",

    7: "Malayalam",

    8: "Tamil",

    9: "Bengali",

    10: "Odia",

    11: "Telugu",

    12: "Kannada",

    13: "Assamese",

    14: "Bhojpuri",

    15: "Urdu",

    16: "Nepali",

    21: "Other"

}


# ============================================================
# CATEGORY ID MAP
# ============================================================

CATEGORY_MAP = {

    5: "Entertainment",

    6: "Movies",

    7: "Kids",

    8: "Sports",

    9: "Music",

    10: "Infotainment",

    12: "News",

    13: "Music",

    15: "Devotional",

    16: "Business",

    17: "Lifestyle",

    18: "Others"

}


# ============================================================
# HEADERS
# ============================================================

HEADERS = {

    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64; "
        "rv:153.0) "
        "Gecko/20100101 Firefox/153.0"
    ),

    "Accept": (
        "application/json, "
        "text/plain, */*"
    ),

    "Accept-Language": (
        "en-US,en;q=0.5"
    ),

    "Connection": "keep-alive"

}


# ============================================================
# GET CHANNELS
# ============================================================

def get_channels():

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    print(
        "Fetching channel list..."
    )

    try:

        response = session.get(
            API_URL,
            timeout=30
        )

        print(
            "HTTP Status:",
            response.status_code
        )

        response.raise_for_status()

        data = response.json()


    except requests.exceptions.ConnectionError as e:

        print(
            "\nConnection error:"
        )

        print(e)

        print(
            "\nThe domain could not be "
            "resolved/reached."
        )

        return []


    except requests.exceptions.Timeout:

        print(
            "\nRequest timed out."
        )

        return []


    except requests.exceptions.HTTPError as e:

        print(
            "\nHTTP error:"
        )

        print(e)

        print(
            response.text[:1000]
        )

        return []


    except requests.exceptions.JSONDecodeError:

        print(
            "\nAPI did not return valid JSON."
        )

        print(
            response.text[:1000]
        )

        return []


    # ========================================================
    # PROCESS CHANNELS
    # ========================================================

    channels = []


    for channel in data.get(
        "result",
        []
    ):

        channel_id = channel.get(
            "channel_id"
        )

        channel_name = channel.get(
            "channel_name"
        )

        logo_file = channel.get(
            "logoUrl"
        )

        # ----------------------------------------------------
        # LANGUAGE
        # ----------------------------------------------------

        language_id = channel.get(
            "channelLanguageId"
        )

        language_name = LANGUAGE_MAP.get(
            language_id,
            "Unknown"
        )


        # ----------------------------------------------------
        # CATEGORY
        # ----------------------------------------------------

        category_id = channel.get(
            "channelCategoryId"
        )

        category_name = CATEGORY_MAP.get(
            category_id,
            "Unknown"
        )


        # ----------------------------------------------------
        # VALIDATE
        # ----------------------------------------------------

        if (
            channel_id is None
            or
            not channel_name
        ):

            continue


        # ----------------------------------------------------
        # LOGO URL
        # ----------------------------------------------------

        logo_url = None


        if logo_file:

            if (
                logo_file.startswith(
                    "http://"
                )
                or
                logo_file.startswith(
                    "https://"
                )
            ):

                logo_url = logo_file

            else:

                logo_url = (
                    BASE_LOGO_URL
                    +
                    logo_file
                )


        # ----------------------------------------------------
        # ADD CHANNEL
        # ----------------------------------------------------

        channels.append({

            "channel_id": channel_id,

            "channel_name": channel_name,

            "language_id": language_id,

            "language": language_name,

            "category_id": category_id,

            "category": category_name,

            "logoUrl": logo_url

        })


    return channels


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    channels = get_channels()


    if channels:

        # ----------------------------------------------------
        # SAVE CHANNELS.JSON
        # ----------------------------------------------------

        with open(
            "channels.json",
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(

                channels,

                file,

                indent=2,

                ensure_ascii=False

            )


        print()

        print(
            f"Successfully saved "
            f"{len(channels)} channels "
            "to channels.json"
        )


        # ----------------------------------------------------
        # SHOW FIRST 10 CHANNELS
        # ----------------------------------------------------

        print()

        print(
            "First 10 channels:"
        )

        print(
            "-" * 70
        )


        for channel in channels[:10]:

            print(

                f"{channel['channel_id']} | "
                f"{channel['channel_name']} | "
                f"{channel['language']} | "
                f"{channel['category']}"

            )


    else:

        print(
            "\nNo channels were saved."
        )