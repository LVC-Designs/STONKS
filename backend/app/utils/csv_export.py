import csv
import io
from typing import AsyncIterator, List


async def rows_to_csv_stream(
    headers: List[str], rows: List[dict]
) -> AsyncIterator[str]:
    """Convert rows to a streaming CSV response."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    yield output.getvalue()
    output.seek(0)
    output.truncate(0)

    for row in rows:
        writer.writerow(row)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
