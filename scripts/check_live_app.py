"""Check that the running local Streamlit app renders without script exceptions.

Unlike the HTTP health endpoint, this exercises the actual app in a new session.
Run with the project's virtual-environment Python while the server is running.
"""

import sys
from time import monotonic

from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from websockets.sync.client import connect


def main() -> int:
    deadline = monotonic() + 30
    rendered = False
    try:
        with connect(
            "ws://127.0.0.1:8501/_stcore/stream",
            origin="http://127.0.0.1:8501",
            subprotocols=["streamlit"],
            open_timeout=5,
            max_size=20 * 1024 * 1024,
        ) as connection:
            request = BackMsg()
            request.rerun_script.SetInParent()
            connection.send(request.SerializeToString())
            while monotonic() < deadline:
                payload = connection.recv(timeout=max(0.1, deadline - monotonic()))
                message = ForwardMsg()
                message.ParseFromString(payload)
                if message.HasField("delta") and message.delta.HasField("new_element"):
                    element = message.delta.new_element
                    if element.HasField("exception"):
                        error = element.exception
                        print(f"FAIL: {error.type}: {error.message}")
                        return 1
                    rendered = True
                if message.HasField("script_finished"):
                    if not rendered:
                        print("FAIL: app finished without rendering any elements")
                        return 1
                    print("PASS: live app rendered without script exceptions")
                    return 0
        print("FAIL: app did not finish rendering before timeout")
        return 1
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
