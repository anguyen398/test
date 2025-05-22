import csv
import io
from datetime import datetime, date
from scrapy.exporters import CsvItemExporter

class SortedCsvItemExporter(CsvItemExporter):
    def __init__(self, file, **kwargs):
        super().__init__(file, **kwargs)
        self._data = []  # Store data in memory before writing to CSV

        # Ensure file is opened in text mode (not binary)
        if hasattr(file, "write") and "b" in getattr(file, "mode", "b"):
            self.stream = io.TextIOWrapper(file, encoding="utf-8", newline="")
        else:
            self.stream = file

    def export_item(self, item):
        self._data.append(item)  # Store each item in memory

    def finish_exporting(self):
        def parse_date(item):
            """
            Parse the 'date' field from the item and return a datetime object.
            - If the string contains a comma, it is assumed to be a full date.
            - Otherwise, it is treated as a time-only string and combined with today's date.
            """
            date_str = item.get("date", "").strip()
            if not date_str:
                return datetime.min

            # Remove trailing timezone (e.g., "ET") if present.
            if date_str.endswith("ET"):
                date_str = date_str[:-2].strip()

            # If the string contains a comma, assume it's a full date.
            if "," in date_str:
                # Try 24-hour format first.
                try:
                    return datetime.strptime(date_str, "%b %d, %Y, %H:%M")
                except ValueError:
                    # Fallback to 12-hour format.
                    try:
                        return datetime.strptime(date_str, "%b %d, %Y, %I:%M %p")
                    except ValueError:
                        return datetime.min
            else:
                # Otherwise, assume it's only a time.
                try:
                    # Try 24-hour time.
                    time_obj = datetime.strptime(date_str, "%H:%M").time()
                except ValueError:
                    try:
                        # Fallback: try 12-hour time.
                        time_obj = datetime.strptime(date_str, "%I:%M %p").time()
                    except ValueError:
                        return datetime.min
                # Combine today’s date with the parsed time.
                return datetime.combine(date.today(), time_obj)

        # Sort the items by the parsed date (newest first).
        self._data.sort(key=parse_date, reverse=True)

        # Re-format the date field in each item to a consistent full date format.
        for item in self._data:
            dt = parse_date(item)
            if dt != datetime.min:
                # Format as: "Feb 03, 2025, 10:00 ET" (using 24-hour time).
                # If the original item only had a time (e.g., "09:24 ET"),
                # dt will be today’s date with that time.
                item["date"] = dt.strftime("%b %d, %Y, %H:%M") + " ET"

        # Ensure fieldnames are set.
        if not self.fields_to_export:
            self.fields_to_export = list(self._data[0].keys()) if self._data else []

        # Write sorted and reformatted data to CSV.
        # Using quoting=csv.QUOTE_ALL to enclose every field in quotes,
        # which prevents commas or special characters in any field (like the summary)
        # from breaking the CSV formatting.
        writer = csv.DictWriter(self.stream, fieldnames=self.fields_to_export, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(self._data)
        self.stream.flush()
