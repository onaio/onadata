# Export select choices with their name or labels

Add an boolean export parameter `show_choice_labels` that will accept `true` or `false`. This option will allow the labels of choices to be included in the submission data being exported. For each row where there is a choice was selected the user will see the label of the choice instead of the choice itself.

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

With the export parameter `show_choice_labels=true` then we have the same export as:

    | fruit  | meta/instanceID |
    | Orange | a1234567890abcd |
    | Mango  | b1234567789efgh |

For select multiple questions:

    | survey  |
    |         | type                   | name  | label  |
    |         | select_multiple fruits | fruit | Fruit  |
    |         |                        |       |        |
    | choices | list name              | name  | label  |
    |         | fruits                 | 1     | Mango  |
    |         | fruits                 | 2     | Orange |
    |         | fruits                 | 3     | Apple  |

The export currently will look like:

    | fruit | meta/instanceID |
    | 1 2   | a1234567890ijkl |
    | 2 3   | b1234567789mnop |

With the export parameter `show_choice_labes=true` then we have the same export as:

    | fruit        | meta/instanceID |
    | Mango Orange | a1234567890ijkl |
    | Orange Apple | b1234567789mnop |

For select multiple questions where the parameter `value_select_multiples` is `true` and `split_select_multiples` is also true, the export will be as:

    | fruit        | fruit/1 | fruit/2  | fruit/3 | meta/instanceID |
    | Mango Orange | Mango   | Orange   |         | a1234567890ijkl |
    | Orange Apple |         | Orange   | Apple   | b1234567789mnop |

With `include_labels=true`:

    | fruit | fruit/Mango | fruit/Orange  | fruit/Apple | meta/instanceID |
    | 1 2   | Mango       | Orange        |             | a1234567890ijkl |
    | 2 3   |             | Orange        | Apple       | b1234567789mnop |
