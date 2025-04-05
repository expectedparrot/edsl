# ScenarioList Source Refactoring Checklist

This document outlines the refactoring process to move the `from_X` methods from `ScenarioList` to child classes of `Source`.

## Refactoring Process

For each source type, follow these steps:

1. Create a new child class of `Source` in `scenario_source.py`
2. Add a deprecated classmethod in `ScenarioList` that references the new source class
3. Run pytest to confirm everything works correctly
4. Move to the next source type

## Source Types Checklist

- [x] `urls` - Already implemented as `URLSource`
- [x] `list` - Already implemented as `ListSource`
- [x] `directory` - Implemented as `DirectorySource`
- [x] `list_of_tuples` - Implemented as `TuplesSource`
- [x] `sqlite` - Implemented as `SQLiteSource`
- [x] `latex` - Implemented as `LaTeXSource`
- [x] `google_doc` - Implemented as `GoogleDocSource`
- [x] `pandas` - Implemented as `PandasSource`
- [x] `dta` - Implemented as `StataSource`
- [x] `wikipedia` - Implemented as `WikipediaSource`
- [x] `excel` - Implemented as `ExcelSource`
- [ ] `google_sheet` - Implement as `GoogleSheetSource`
- [ ] `delimited_file` - Implement as `DelimitedFileSource`
- [ ] `csv` - Implement as `CSVSource` (extending `DelimitedFileSource`)
- [ ] `tsv` - Implement as `TSVSource` (extending `DelimitedFileSource`)
- [ ] `dict` - Implement as `DictSource`
- [ ] `nested_dict` - Implement as `NestedDictSource`
- [ ] `parquet` - Implement as `ParquetSource`
- [ ] `pdf` - Implement as `PDFSource`
- [ ] `pdf_to_image` - Implement as `PDFImageSource`