# Export with submission review fields
 Add an boolean export parameter `include_reviews` that will accept `true` or `false`. This option will allow the review_status and review_comments field to be included in the submissions data being exported.
 Given the XLSForm:
     | survey  |
    |         | type              | name  | label  |
    |         | select one fruits | fruit | Fruit  |
    |         |                   |       |        |
    | choices | list name         | name  | label  |
    |         | fruits            | 1     | Mango  |
    |         | fruits            | 2     | Orange |
    |         | fruits            | 3     | Apple  |
 The export currently will look like:
     | fruit | meta/instanceID |
    | 2     | a1234567890abcd |
    | 1     | b1234567789efgh |
 With the export parameter `include_reviews=true` then we have the same export as:
     | fruit  | meta/instanceID | review_status | review_comments
    | Orange | a1234567890abcd  | rejected       | unreasonable prices
    | Mango  | b1234567789efgh  | accepted       | well done
 