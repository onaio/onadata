# Bulk data upload.

Allow bulk upload of data.

1. CSV upload to a blank form (already supported)
2. Excel upload to a blank form (not supported)
3. Allow multiple uploads of data to a form that may already include data.

Example XLSForm:

    | survey  |
    |         | type              | name    | label      |
    |         | text              | a_name  | Your Name? |
    |         | begin group       | fruits  | Fruits     |
    |         | select one fruits | fruit   | Fruit      |
    |         | end group         |         |            |
    |         |                   |         |            |
    | choices | list name         | name    | label      |
    |         | fruits            | mango   | Mango      |
    |         | fruits            | orange  | Orange     |
    |         | fruits            | apple   | Apple      |

## Excel bulk data upload to an existing form

A user should be able to upload an Excel `.xls/.xlsx` file to a form. The data in the file will add new submissions or edit submissions. The excel file should have:

1. The first row, the column header row, MUST HAVE the name that matches a question name in the XLSForm/XForm form. Any column name that does not match a question in the form will be ignored and hence not imported.
2. The column header names MAY HAVE group or repeat name separators. If there are no separators, it will be ASSUMED that the field name matches the question be it within a group or a repeat. For example:

    | a_name | fruits/fruit |
    | Alice  | mango        |
    | Bob    | orange       |

Without the group name, it will also match perfectly to the above form.

    | a_name | fruit  |
    | Alice  | mango  |
    | Bob    | orange |

3. There MUST NOT be a duplicate named column in the form or the data upload file otherwise it will be rejected.
4. The file MAY HAVE a `meta/instanceID` column which should uniquely identify a specific record. If present, the `meta/instanceID` will be used to identify whether the record is new or is an edit. If it does not exist, the system will create a new one for each new record added.

Questions:
1. What happens if an upload file has repeats? They will also be uploaded, they need to be in the flat csv format, e.g `fruits[1]/fruit`.

2. Which Excel sheet should have the data imported? First sheet.
3. Should an Excel template file be provided? Yes, need to implement a blank CSV format - it will be upto the user to convert the CSV to excel.

### Data upload expected behaviour

When the upload is complete, three things could happen to the data.2

1. The upload will add new records to the existing form.
2. The upload will edit existing records where there is a matching `meta/instanceID` and add new records if the existing `meta/instanceID` is either blank or missing or does not exist.
3. The upload will overwrite existing records.

Note:

- For ANY approach, the UI should display a caution/warning, and a clear explanation of expected behaviour to the user.
- There will be the loss of the original data submitter information in the case of an overwrite.
- No effort will be made to link an exported file from Ona with the original submitter of the data.

#### 1. The upload will add new records to the existing form.

A data upload will add new records to the existing form under the following circumstances:

1. The form has NO submissions.
2. The upload file DOES NOT have the `meta/instanceID` column. (Should the user be allowed to specify a unique column?)

#### 2. The upload will edit existing records

A data upload will edit existing records in an existing form only if the upload file CONTAINS the column `meta/instanceID` and the value in this column MATCHES an existing record in the form.

Note: We will create a new record If the `meta/instanceID` is EITHER BLANK or MISSING or DOES NOT EXIST.

#### 3. The upload will OVERWRITE existing record

A data will OVERWRITE existing records if the parameter `overwrite` is `true`, `overwrite=true`, as part of the upload request. All existing records will be PERMANENTLY DELETED, and the NEW data upload will become the new submissions in the form.

Questions:
- Should it be possible to REVERT this process? NO


## API implementation

Implement a `/api/v1/data/[pk]/import` or endpoint on the API.

### `POST` /data/[pk]/import

The endpoint will accept `POST` requests to upload the data CSV/Excel file.

- Persist the uploaded file in the database and file storage. I propose we use the `MetaData` model to keep this record; we may need to use a new key, e.g. `data-imports` to refer to this files. New models could be used to achieve the same effect if there is more information to be stored.
- An asynchronous task will be created to start the process of importing the records from the file.

Request:

    POST /data/[pk]/import

    {
        "upload_file": ...,  // the file to upload
        "overwrite": false, // whether to overwrite or not, accepts true or false.
        ...
    }

Response:

    Response status code 201

    {
        "xform": [xform pk],
        "upload_id": [unique record identify for the upload]
        "filename": [filename of uploaded file]
    }

#### Processing the Uploaded file.

Depending on the query parameters, the data import will be taking into account the three options available as described above, i.e., NEW or EDIT or OVERWRITE.

- A record of the number of records processed, successful and failed should be maintained.
- In the event of a SUCCESS or a FAILURE, a notification SHOULD be sent. The notification can be via EMAIL to the user uploading the data or to via MQTT messaging/notifications or BOTH.

## Questions

1. What happens if an upload file has repeats? Repeats will be part of data.
2. Which Excel sheet should have the data imported? The first sheet.
3. Should an Excel template file be provided? Yes, API endpoint will be added.
4. Should it be possible to REVERT this process? NO
5. How should we notify the user of upload status/progress? messaging notification, job status query?
6. What limits should we impose on data file uploads? In megabytes or number rows?
7. Is the process supposed to be atomic - i.e. all uploads go through, or partial uploads will do? Partial uploads to be supported.
8. Should data imports from exports link the submitted by the user? Yes.
9. Should media links be downloaded into the new submission? Only data will be imported; media attachments will not be imported.
