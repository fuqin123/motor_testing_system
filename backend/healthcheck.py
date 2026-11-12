"""容器健康检查：绕过 HTTP 代理，直接访问本机 API。"""

import http.client
import os
import sys


def main() -> int:
    port = int(os.getenv("MP_API_PORT", "8000"))
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        connection.request("GET", "/api/v1/health")
        response = connection.getresponse()
        return 0 if response.status == 200 else 1
    except OSError:
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    sys.exit(main())
