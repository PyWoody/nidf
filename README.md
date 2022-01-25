# nidf
### Simple, striped down `find` replacement for use on NAS or slow disk drives. Results may be faster than `find` on SSDs for deep but not shallow searches. 

The "-z/--zips" flag will allow you to search inside zip-like objects.

The "--hash" option accepts an absolute filepath to generate a hash to search against.

You can combine the `--hash` and `-z/--zips` options to search for hashes in zip-like objects as well. For example,

```
py -m nidf /starting/path --hash /path/to/file.txt -z
```

will search starting for hash matches for `/path/to/file.txt` starting from `/starting/path` as well as in any zip-like objects.

Zip-like objects include `.zip`, `.docx`, `.pptx`, `.xlsxl`, `.epub`, and more!

NOTE: It is important to recognize caches. If you are going to do any tests directly against `find`, I suggest running them multiple times to make sure they each can benefit from the cache.

### Options/Flags
```
  -name NAME       Case sensitive search. Accepts basic regular expressions.
  -iname INAME     Case insensitive search. Accepts basic regular expressions.
  --hash HASH      Flag for searching in archives. Default is False.
  -type {d,f}      "f" for file; "d" for directory. Ignore for either.
  -z, --zips       Flag for searching in archives. Default is False.
  --ignore_errors  Flag for suppressing OSErrors. Default is False.
```
