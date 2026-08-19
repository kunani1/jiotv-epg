import requests
import json
import os
import time
import random

from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed


# ============================================================
# CONFIG
# ============================================================

CHANNELS_FILE = "channels.json"

OUTPUT_FOLDER = "channels"


# ============================================================
# EPG API
# ============================================================

EPG_API_URL = (
    "https://jiotvapi.cdn.jio.com/apis/v1.3/getepg/get"
    "?channel_id={channel_id}"
    "&offset={offset}"
)


# ============================================================
# CONCURRENT CHANNELS
# ============================================================

# 50 channels at a time
BATCH_SIZE = 50


# ============================================================
# RETRY SETTINGS
# ============================================================

MAX_RETRIES = 4

REQUEST_TIMEOUT = 30


# ============================================================
# OFFSETS
# ============================================================

OFFSETS = [
    -1,
    0,
    1,
    2,
    3,
    4,
    5,
    6
]


# ============================================================
# EPG IMAGE URL
# ============================================================

EPG_IMAGE_URL = (
    "https://jiotvimages.cdn.jio.com/"
)


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

    "Referer": (
        "https://www.jiotv.com/"
    ),

    "Origin": (
        "https://www.jiotv.com"
    ),

    "Connection": "keep-alive",

    "Cache-Control": "no-cache"

}


# ============================================================
# LOAD CHANNELS.JSON
# ============================================================

def load_channels():

    if not os.path.exists(
        CHANNELS_FILE
    ):

        print(
            f"ERROR: {CHANNELS_FILE} "
            "not found."
        )

        return []


    try:

        with open(
            CHANNELS_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)


    except Exception as e:

        print(
            "ERROR reading channels.json:"
        )

        print(e)

        return []


    if not isinstance(
        data,
        list
    ):

        print(
            "ERROR: channels.json "
            "must contain a JSON array."
        )

        return []


    return data


# ============================================================
# THUMBNAIL URL
# ============================================================

def get_thumbnail_url(path):

    if not path:

        return None


    if (
        path.startswith("http://")
        or
        path.startswith("https://")
    ):

        return path


    path = path.lstrip("/")


    return (
        EPG_IMAGE_URL
        +
        path
    )


# ============================================================
# SERVER DATE
# ============================================================

def get_server_date(
    server_date
):

    if not server_date:

        return None


    try:

        dt = datetime.fromisoformat(
            server_date
        )

        return dt.strftime(
            "%Y-%m-%d"
        )


    except Exception:

        return server_date.split(
            "T"
        )[0]


# ============================================================
# CREATE DATETIME
# ============================================================

def create_datetime(
    server_date,
    time_string
):

    if (
        not server_date
        or
        not time_string
    ):

        return None


    try:

        date_part = datetime.strptime(
            server_date,
            "%Y-%m-%d"
        ).date()


        time_part = datetime.strptime(
            time_string,
            "%H:%M:%S"
        ).time()


        result = datetime.combine(
            date_part,
            time_part
        )


        return result.strftime(
            "%Y-%m-%dT%H:%M:%S"
        )


    except Exception:

        return None


# ============================================================
# PROCESS PROGRAM
# ============================================================

def process_program(
    program,
    offset_server_date
):

    showtime = program.get(
        "showtime"
    )

    endtime = program.get(
        "endtime"
    )


    # --------------------------------------------------------
    # SAME DATE FOR ALL PROGRAMS OF THIS OFFSET
    # --------------------------------------------------------

    server_date = offset_server_date


    # --------------------------------------------------------
    # START DATE
    # --------------------------------------------------------

    start_date = create_datetime(
        server_date,
        showtime
    )


    # --------------------------------------------------------
    # END DATE
    # --------------------------------------------------------

    end_date = create_datetime(
        server_date,
        endtime
    )


    # --------------------------------------------------------
    # MIDNIGHT HANDLING
    # --------------------------------------------------------

    if (
        start_date
        and
        end_date
        and
        end_date < start_date
    ):

        try:

            end_dt = datetime.strptime(
                end_date,
                "%Y-%m-%dT%H:%M:%S"
            )


            end_dt += timedelta(
                days=1
            )


            end_date = end_dt.strftime(
                "%Y-%m-%dT%H:%M:%S"
            )


        except Exception:

            pass


    # --------------------------------------------------------
    # THUMBNAIL
    # --------------------------------------------------------

    thumbnail = (

        program.get(
            "episodeThumbnail"
        )

        or

        program.get(
            "episodePoster"
        )

    )


    thumbnail_url = (
        get_thumbnail_url(
            thumbnail
        )
    )


    # --------------------------------------------------------
    # PROGRAM OUTPUT
    # --------------------------------------------------------

    return {

        "serverDate": server_date,

        "showName": program.get(
            "showname"
        ),

        "description": program.get(
            "description"
        ),

        "startDate": start_date,

        "endDate": end_date,

        "showTime": showtime,

        "endTime": endtime,

        "showCategory": program.get(
            "showCategory"
        ),

        "thumbnailUrl": thumbnail_url

    }


# ============================================================
# EXTRACT EPG
# ============================================================

def extract_epg(data):

    if not isinstance(
        data,
        dict
    ):

        return []


    # --------------------------------------------------------
    # { "epg": [...] }
    # --------------------------------------------------------

    if isinstance(
        data.get("epg"),
        list
    ):

        return data["epg"]


    # --------------------------------------------------------
    # { "result": [...] }
    # --------------------------------------------------------

    if isinstance(
        data.get("result"),
        list
    ):

        return data["result"]


    # --------------------------------------------------------
    # { "data": [...] }
    # --------------------------------------------------------

    if isinstance(
        data.get("data"),
        list
    ):

        return data["data"]


    # --------------------------------------------------------
    # { "result": { "epg": [...] } }
    # --------------------------------------------------------

    result = data.get(
        "result"
    )


    if isinstance(
        result,
        dict
    ):

        if isinstance(
            result.get("epg"),
            list
        ):

            return result["epg"]


        if isinstance(
            result.get("data"),
            list
        ):

            return result["data"]


    return []


# ============================================================
# GET EPG WITH RETRIES
# ============================================================

def get_epg(
    session,
    channel_id,
    offset
):

    url = EPG_API_URL.format(

        channel_id=channel_id,

        offset=offset

    )


    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):

        try:

            response = session.get(
                url,
                timeout=REQUEST_TIMEOUT
            )


            status = response.status_code


            # =================================================
            # HTTP 450
            # =================================================

            if status == 450:

                # ---------------------------------------------
                # Check Retry-After header
                # ---------------------------------------------

                retry_after = response.headers.get(
                    "Retry-After"
                )


                if retry_after:

                    try:

                        wait_time = float(
                            retry_after
                        )

                    except ValueError:

                        wait_time = 5

                else:

                    # -----------------------------------------
                    # Exponential backoff + random jitter
                    #
                    # Attempt 1 -> around 3 sec
                    # Attempt 2 -> around 6 sec
                    # Attempt 3 -> around 12 sec
                    # -----------------------------------------

                    wait_time = (
                        3 * (2 ** (attempt - 1))
                        +
                        random.uniform(
                            0.5,
                            2.5
                        )
                    )


                if attempt < MAX_RETRIES:

                    print(
                        f"      Channel "
                        f"{channel_id} "
                        f"Offset {offset}: "
                        f"HTTP 450 "
                        f"retry {attempt}/"
                        f"{MAX_RETRIES} "
                        f"after "
                        f"{wait_time:.1f}s"
                    )


                    time.sleep(
                        wait_time
                    )


                    continue


                print(
                    f"      Channel "
                    f"{channel_id} "
                    f"Offset {offset}: "
                    f"HTTP 450 after "
                    f"{MAX_RETRIES} attempts"
                )


                return []


            # =================================================
            # RATE LIMITING
            # =================================================

            if status == 429:

                retry_after = response.headers.get(
                    "Retry-After"
                )


                if retry_after:

                    try:

                        wait_time = float(
                            retry_after
                        )

                    except ValueError:

                        wait_time = 10

                else:

                    wait_time = (
                        5 * (2 ** (attempt - 1))
                        +
                        random.uniform(
                            1,
                            3
                        )
                    )


                if attempt < MAX_RETRIES:

                    print(
                        f"      Channel "
                        f"{channel_id} "
                        f"Offset {offset}: "
                        f"HTTP 429 "
                        f"waiting "
                        f"{wait_time:.1f}s"
                    )


                    time.sleep(
                        wait_time
                    )


                    continue


                print(
                    f"      Channel "
                    f"{channel_id} "
                    f"Offset {offset}: "
                    f"HTTP 429"
                )


                return []


            # =================================================
            # OTHER HTTP ERRORS
            # =================================================

            response.raise_for_status()


            # =================================================
            # JSON
            # =================================================

            data = response.json()


            return extract_epg(
                data
            )


        # =====================================================
        # CONNECTION / TIMEOUT
        # =====================================================

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout
        ) as e:


            if attempt < MAX_RETRIES:

                wait_time = (
                    2 ** attempt
                    +
                    random.uniform(
                        0.5,
                        2
                    )
                )


                print(
                    f"      Channel "
                    f"{channel_id} "
                    f"Offset {offset}: "
                    f"connection error "
                    f"retrying in "
                    f"{wait_time:.1f}s"
                )


                time.sleep(
                    wait_time
                )


                continue


            print(
                f"      Channel "
                f"{channel_id} "
                f"Offset {offset} "
                f"ERROR: {e}"
            )


            return []


        # =====================================================
        # INVALID JSON
        # =====================================================

        except requests.exceptions.JSONDecodeError:

            print(
                f"      Channel "
                f"{channel_id} "
                f"Offset {offset}: "
                "Invalid JSON"
            )


            return []


        # =====================================================
        # OTHER REQUEST ERROR
        # =====================================================

        except requests.exceptions.RequestException as e:

            print(
                f"      Channel "
                f"{channel_id} "
                f"Offset {offset} "
                f"ERROR: {e}"
            )


            return []


        except Exception as e:

            print(
                f"      Channel "
                f"{channel_id} "
                f"Offset {offset} "
                f"ERROR: {e}"
            )


            return []


    return []


# ============================================================
# PROCESS ONE CHANNEL
# ============================================================

def process_channel(
    channel
):

    # --------------------------------------------------------
    # CHANNEL INFORMATION
    # --------------------------------------------------------

    channel_id = channel.get(
        "channel_id"
    )


    channel_name = channel.get(
        "channel_name"
    )


    logo_url = channel.get(
        "logoUrl"
    )


    # --------------------------------------------------------
    # LANGUAGE
    # --------------------------------------------------------

    language_id = channel.get(
        "language_id"
    )


    language = channel.get(
        "language"
    )


    # --------------------------------------------------------
    # CATEGORY
    # --------------------------------------------------------

    category_id = channel.get(
        "category_id"
    )


    category = channel.get(
        "category"
    )


    if channel_id is None:

        return (
            False,
            None,
            "Missing channel_id"
        )


    # --------------------------------------------------------
    # SESSION
    # --------------------------------------------------------

    session = requests.Session()

    session.headers.update(
        HEADERS
    )


    all_programs = []


    # ========================================================
    # OFFSETS
    # ========================================================

    for offset in OFFSETS:

        epg_data = get_epg(

            session,

            channel_id,

            offset

        )


        if not epg_data:

            continue


        # ----------------------------------------------------
        # GET SERVER DATE
        # ----------------------------------------------------

        offset_server_date = None


        for program in epg_data:

            raw_server_date = (
                program.get(
                    "serverDate"
                )
            )


            if raw_server_date:

                offset_server_date = (
                    get_server_date(
                        raw_server_date
                    )
                )

                break


        if not offset_server_date:

            continue


        print(
            f"Channel {channel_id} | "
            f"Offset {offset} | "
            f"Date {offset_server_date} | "
            f"Programs {len(epg_data)}"
        )


        # ----------------------------------------------------
        # PROCESS PROGRAMS
        # ----------------------------------------------------

        for program in epg_data:

            program_channel_id = (
                program.get(
                    "channel_id"
                )
            )


            # Ignore programs from another channel

            if (

                program_channel_id is not None

                and

                str(
                    program_channel_id
                )

                !=

                str(
                    channel_id
                )

            ):

                continue


            processed = process_program(

                program,

                offset_server_date

            )


            all_programs.append(
                processed
            )


    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    unique_programs = {}


    for program in all_programs:

        key = (

            program.get(
                "serverDate"
            ),

            program.get(
                "showTime"
            ),

            program.get(
                "endTime"
            ),

            program.get(
                "showName"
            )

        )


        unique_programs[key] = (
            program
        )


    all_programs = list(
        unique_programs.values()
    )


    # ========================================================
    # SORT
    # ========================================================

    all_programs.sort(

        key=lambda x: (

            x.get(
                "startDate"
            )

            or

            ""

        )

    )


    # ========================================================
    # OUTPUT DIRECTORY
    # ========================================================

    os.makedirs(

        OUTPUT_FOLDER,

        exist_ok=True

    )


    # ========================================================
    # FINAL JSON
    # ========================================================

    channel_output = {

        "channel_id": channel_id,

        "channel_name": channel_name,

        "language_id": language_id,

        "language": language,

        "category_id": category_id,

        "category": category,

        "logoUrl": logo_url,

        "programs": all_programs

    }


    # ========================================================
    # SAVE
    # ========================================================

    output_file = os.path.join(

        OUTPUT_FOLDER,

        f"{channel_id}.json"

    )


    try:

        with open(

            output_file,

            "w",

            encoding="utf-8"

        ) as file:

            json.dump(

                channel_output,

                file,

                indent=2,

                ensure_ascii=False

            )


    except Exception as e:

        return (

            False,

            channel_id,

            str(e)

        )


    return (

        True,

        channel_id,

        len(all_programs)

    )


# ============================================================
# PROCESS BATCH
# ============================================================

def process_batch(

    batch,

    batch_number,

    total_batches

):

    print()

    print(
        "=" * 70
    )


    print(
        f"BATCH "
        f"{batch_number}/"
        f"{total_batches}"
    )


    print(
        f"Channels: "
        f"{len(batch)}"
    )


    print(
        "=" * 70
    )


    completed = 0

    failed = 0


    # --------------------------------------------------------
    # 50 CHANNELS CONCURRENTLY
    # --------------------------------------------------------

    with ThreadPoolExecutor(

        max_workers=BATCH_SIZE

    ) as executor:


        futures = {

            executor.submit(

                process_channel,

                channel

            ): channel

            for channel in batch

        }


        for future in as_completed(
            futures
        ):

            channel = futures[
                future
            ]


            channel_id = channel.get(
                "channel_id"
            )


            channel_name = channel.get(
                "channel_name"
            )


            try:

                success, result_id, result = (
                    future.result()
                )


                if success:

                    completed += 1


                    print(

                        f"[OK] "

                        f"{result_id} - "

                        f"{channel_name} - "

                        f"{result} programs"

                    )


                else:

                    failed += 1


                    print(

                        f"[FAILED] "

                        f"{channel_id} - "

                        f"{channel_name} - "

                        f"{result}"

                    )


            except Exception as e:

                failed += 1


                print(

                    f"[FAILED] "

                    f"{channel_id} - "

                    f"{channel_name} - "

                    f"{e}"

                )


    print()

    print(
        f"Batch {batch_number} completed"
    )


    print(
        f"Successful: {completed}"
    )


    print(
        f"Failed: {failed}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print(
        "=" * 70
    )


    print(
        "JIO TV EPG CHANNEL GENERATOR"
    )


    print(
        "=" * 70
    )


    # --------------------------------------------------------
    # LOAD CHANNELS
    # --------------------------------------------------------

    channels = load_channels()


    if not channels:

        print(
            "No channels found."
        )

        return


    print(
        f"Total channels: "
        f"{len(channels)}"
    )


    print(
        f"Concurrent channels: "
        f"{BATCH_SIZE}"
    )


    print(
        f"Offsets: "
        f"{OFFSETS}"
    )


    print(
        f"Maximum retries: "
        f"{MAX_RETRIES}"
    )


    # --------------------------------------------------------
    # OUTPUT DIRECTORY
    # --------------------------------------------------------

    os.makedirs(

        OUTPUT_FOLDER,

        exist_ok=True

    )


    # --------------------------------------------------------
    # CREATE BATCHES
    # --------------------------------------------------------

    batches = [

        channels[
            i:i + BATCH_SIZE
        ]

        for i in range(

            0,

            len(channels),

            BATCH_SIZE

        )

    ]


    total_batches = len(
        batches
    )


    print(
        f"Total batches: "
        f"{total_batches}"
    )


    # --------------------------------------------------------
    # PROCESS BATCHES
    # --------------------------------------------------------

    for index, batch in enumerate(

        batches,

        start=1

    ):

        process_batch(

            batch,

            index,

            total_batches

        )


    # --------------------------------------------------------
    # COMPLETE
    # --------------------------------------------------------

    print()

    print(
        "=" * 70
    )


    print(
        "ALL CHANNELS COMPLETED"
    )


    print(
        "=" * 70
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
