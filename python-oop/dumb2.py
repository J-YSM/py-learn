@init

#==============================================================================
# # Let users know if they're missing any of our hard dependencies
#==============================================================================
hard_dependencies = ("yaml", "numpy", "pandas", "sys")
missing_dependencies = []

for dependency in hard_dependencies:
    try:
        __import__(dependency)
    except ImportError as e:
        missing_dependencies.append(dependency)

if missing_dependencies:
    raise ImportError(
        "Missing required dependencies {0}".format(missing_dependencies))
del hard_dependencies, dependency, missing_dependencies


#==============================================================================
# expand namespace
#==============================================================================

from proj_query_engine.core import *
from proj_query_engine.util import *


# module level doc-string
__doc__ = """
query engine - decomposed canonical tree query steps
=====================================================================

Inputs engine steps via YAML. 
Need to self optimise queries. 

Main Features
-------------
Here are just a few of the things that it does well:
    - extraction
    - transformation
    
"""


@core.py

import pandas as pd
# use lazy evaluation
#import dask.dataframe as pd11

import abc
from proj_query_engine.util import *

class engine(metaclass=abc.ABCMeta):
    """
    Define methods an engine should have
    """
    __slots__ = ('_data','_writer')
    @abc.abstractmethod
    def top(self):
        pass
    @abc.abstractmethod
    def bottom(self):
        pass



class query_engine(engine):
    __doc__ = """
    ==========================================
    DESCRIPTION
    ==========================================
    - All purpose data flow with ETL
    - Uses containers to allow reuse of queries output for other queries
    - Configuration will be in YAML
    """

    @timeit
    def __init__(self, dest_path, 
                 cfg_csv_list = None, cfg_excel_list= None, 
                 checkMemory = False,
                 *args, **kwargs):
#        pd.set_option('display.float_format', lambda x: '%.7f' % x)
        self._writer = pd.ExcelWriter(dest_path) # read SFTP file
        self._data = {'primary':None} # e.g. {container label: dataframe1}
        
        #load data
        self.load_data(cfg_csv_list, cfg_excel_list)
        
        # prettify colnames e.g. from R output
        for df_name, df in self._data.items():
            if not df is None:
                self._data[df_name] = prettify_colnames_from_R(df)

        # monitor heap size for each container in dict
        if checkMemory: self.check_memory()
        
        
    def closewb(self):
        # write pivot table into a sheet
        # https://pandas.pydata.org/pandas-docs/stable/options.html
        for k,v in self._data.items():
            if isinstance(v,pd.core.frame.DataFrame):
                print('writing sheet '+ k + '...')
                v.to_excel(self._writer, sheet_name = k, 
                           index = True, header = True, na_rep='', inf_rep='',
                           merge_cells = False, float_format = '%.7f',
                           encoding = 'iso-8859-1')
            else:
                print("None to write into excel for container: " + k)
        self._writer.close()


    def check_memory(self):
        memory_usage(self._data)
        python_memory_usage()
        pass
    
    # reader extension : file from database by query engine
    def open_flatfile(self, reader, append_to=None, dummycol=None, **kwargs):
        '''
         layer to control data flow for append_to dummycol 
         **kwargs is passed in from config_file: supported --> csv, excel
        '''        
        df = reader(**kwargs)
        if append_to is None:
            # default container label name
            append_to = 'primary'
        if not dummycol is None:
            # append new column for pivoting
            df = append_dummycol(df, dummycol)
        
        if self._data[append_to] is None:
            print("appending df to empty container: " + append_to)
            self._data[append_to] = df
            print(self._data[append_to].head(5))
        else: # append
            print("appending df to filled container: " + append_to)
            self._data[append_to] = self._data[append_to].append(df)
            print(self._data[append_to].head(5))

    def load_data(self, cfg_csv_list, cfg_excel_list):
        """ Given configurations in list for each file 
            in __init__ to setup data in containers """
        if not cfg_csv_list is None:
            for _csv in cfg_csv_list:
                #extra_kwargs:
                # @append to which file?
                # @dummyvar if there is no column to pivot on
                kwargs, extra_kwargs = relevant_kw(f=pd.read_csv, kw=_csv)
                print("kwargs: " + str(kwargs))
                print("extra_kwargs: " + str(extra_kwargs))
                
                # how many files to append?
                if extra_kwargs['append'] not in self._data.keys():
                    self._data[extra_kwargs['append']] = None
                
                # preprocessing layer before storing in container
                self.open_flatfile(reader, 
                              append_to = extra_kwargs['append'], 
                              dummycol = extra_kwargs['dummycol'], 
                              **kwargs)

        if not cfg_excel_list is None:
            for _wb in cfg_excel_list:

                kwargs, extra_kwargs = relevant_kw(f=pd.read_excel, kw=_wb)

                if extra_kwargs['append'] not in self._data.keys():
                    self._data[extra_kwargs['append']] = None
    
                self.open_flatfile(reader, 
                              append_to = extra_kwargs['append'], 
                              dummycol = extra_kwargs['dummycol'], 
                              **kwargs)


    def append(self, containers_to_append, 
               input_container, output_container):
        '''
        @containers_to_append: str or list (containers to append to output)
        '''        
        for container in containers_to_append:
            if container in list(self._data.keys()):
                self._data[output_container].append(self._data[container])
            else: 
                print(container + " not in any containers")
                

    def top(self, input_container, output_container, by=None, n=10):
        """
        @by: column to sort descending (largest nth entries)
        @n: top n rows
        """        
        self._data[output_container] = sort_column(
                self._data[input_container], colname = by, ascending=False).head(n)

    def bottom(self, input_container, output_container, by=None, n=10):
        """
        @by: column to sort ascending (smallest nth entries)
        @n: top n rows
        """
        self._data[output_container] = sort_column(
                self._data[input_container], colname = by, ascending=True).head(n)


    def crosstab(self, input_container, output_container, 
                 values=None, index=None, 
                 aggfunc=None, columns=None, 
                 margins=True,margins_name='Total',
                 dropna=True, fill_value=0):
        '''
        - Same as excel workbook pivot tables
        @values: str, one column
        @index: str or list
        @columns: categorical columns
        @aggfunc: is function or list of functions
        @margins: True (Total for all rows and columns)
        @margins_name: Total
        @fill_value=0        
        '''            
        self._data[output_container] = pd.pivot_table(self._data[input_container], 
             values=values, index=index,
             columns=columns, aggfunc= aggfunc,
             margins=margins, dropna=dropna, 
             margins_name=margins_name, fill_value=fill_value)

        if isinstance(aggfunc, list):
            self._data[output_container].columns = \
                [x[1] + " " + x[0] for x in 
                 list(self._data[output_container].columns.values)]
        elif callable(aggfunc):
            self._data[output_container].columns = \
                [x + " " + aggfunc.__name__ for x in 
                 list(self._data[output_container].columns.values)]
        else:
            print("Invalid cross tab aggfunc type")


    def groupby(self, input_container, output_container, 
                by=None, values=None, aggregation=None):
         '''
         @index: can be composite >1 columns for unstacking into cross tab later
         @values: column where aggregation is applied
         @aggregation: any function on pd.Series e.g. np.sum
         '''
         self._data[output_container] = self._data[input_container]\
             .groupby(by, axis=0)[values]\
             .apply(aggregation)

    def select(self, columns, input_container, output_container):
        '''
        @columns: list or str
        - keep 1 or more columns from container
        - copying data if output container differs from input container
        '''
        self._data[output_container] = self._data[input_container][columns]

    def deselect(self, columns, input_container, output_container):
        '''
        @columns: list or str
        - remove 1 or more columns from container
        - copying data if output container differs from input container
        '''
        self._data[output_container] = self._data[input_container].drop(columns, axis=1)
        
    def filter(self, input_container=None, output_container=None, **conditions):
        '''
        @**conditions: {colname : condition}
        - filter based on numeric range or category levels
        '''
        for column, condition in conditions.items():
            print("Filtering " + column + " by " + condition)
            
            if condition.startswith('<='):                
                self._data[output_container] = self._data[input_container]\
                .loc[self._data[input_container][column]\
                     <= str_to_numeric(condition.lstrip('<=')),:]
                
            elif condition.startswith('>='):
                self._data[output_container] = self._data[input_container]\
                .loc[self._data[input_container][column]\
                     >= str_to_numeric(condition.lstrip('>=')),:]

            elif condition.startswith('='):
                self._data[output_container] = self._data[input_container]\
                .loc[self._data[input_container][column]\
                     == str_to_numeric(condition.lstrip('=')),:]
        
            elif condition.startswith('<'):
                self._data[output_container] = self._data[input_container]\
                .loc[self._data[input_container][column]\
                     < str_to_numeric(condition.lstrip('<')),:]
        
            elif condition.startswith('>'):
                self._data[output_container] = self._data[input_container]\
                .loc[self._data[input_container][column]\
                     > str_to_numeric(condition.lstrip('>')),:]

            else: # string as category levels to fiter
                if isinstance(condition, list):
                    self._data[output_container] = self._data[input_container]\
                    .loc[self._data[output_container][column].isin(condition),:]
                elif isinstance(condition, str):
                    self._data[output_container] = self._data[input_container]\
                    .loc[self._data[input_container][column]\
                         == condition,:]
                
    def startswith(self, input_container=None, output_container=None, **conditions):
        '''
        @**conditions: {colname : condition}
        - filter based on column value starting with some pattern
        '''
        for column, condition in conditions.items():
            print("Filtering " + column + " starting with " + condition)
            self._data[output_container] = self._data[input_container]\
            .loc[self._data[input_container][column].str\
                 .startswith(condition),:]
    
    def endswith(self, input_container=None, output_container=None, **conditions):
        '''
        @**conditions: {colname : condition}
        - filter based on column value ending with some pattern
        '''
        for column, condition in conditions.items():
            print("Filtering " + column + " starting with " + condition)
            self._data[output_container] = self._data[input_container]\
            .loc[self._data[input_container][column].str\
                 .endswith(condition),:]

    def contains(self, input_container=None, output_container=None, **conditions):
        '''
        @**conditions: {colname : condition}
        - filter based on column value containing some pattern
        '''
        for column, condition in conditions.items():
            print("Filtering " + column + " starting with " + condition)
            self._data[output_container] = self._data[input_container]\
            .loc[self._data[input_container][column].str\
                 .contains(condition),:]
    
    def summation(self, name, columns, input_container, output_container):
        '''
        @name: str, the new column name where output of function is 
        @columns: list of column names, where order matters to execution of operator
        - X1+X2+X3+ ...
        '''
        assert isinstance(name, str), "Calculate: summation method"
        assert isinstance(columns, list), "Calculate: summation method"
        print("Performing summation on container " + output_container + 
              " --> " + " + ".join(columns))

        self._data[output_container] = self._data[input_container]
        for i in range(len(columns)-1):
            if i == 0:
                # X + Y
                X = columns[i]
                Y = columns[i+1]
                self._data[output_container][name] = \
                self._data[output_container][X] + self._data[output_container][Y]
            else:
                Y = columns[i+1]
                self._data[output_container][name] = \
                self._data[output_container][name] + self._data[output_container][Y]


    def difference(self, name, columns, input_container, output_container):
        '''
        @name: str, the new column name where output of function is 
        @columns: list of column names, where order matters to execution of operator
        - X1-X2-X3- ...
        '''
        assert isinstance(name, str), "Calculate: difference method"
        assert isinstance(columns, list), "Calculate: difference method"
        print("Performing difference on container " + output_container + 
              " --> " + " - ".join(columns))

        self._data[output_container] = self._data[input_container]
        for i in range(len(columns)-1):
            if i == 0:
                # X- Y
                X = columns[i]
                Y = columns[i+1]
                self._data[output_container][name] = \
                self._data[output_container][X] - self._data[output_container][Y]
            else:
                Y = columns[i+1]
                self._data[output_container][name] = \
                self._data[output_container][name] - self._data[output_container][Y]

    def absolute_difference(self, name, columns, input_container, output_container):
        '''
        @name: str, the new column name where output of function is 
        @columns: list of column names, where order matters to execution of operator
        - ABS(X-Y)
        '''
        self.difference(name, columns, input_container, output_container)
        self._data[output_container][name] = abs(self._data[output_container][name])

    def percentage_difference(self, name, columns, input_container, output_container):
        '''
        @name: str, the new column name where output of function is 
        @columns: list of column names, where order matters to execution of operator
        - (X-Y)/Y Note: divide by 0 gives Inf, divide by Inf gives 0
        '''
        assert len(columns)==2, "percentage_difference only takes in 2 columns"
        
        self.difference(name, columns, input_container, output_container)
        denominator = self._data[output_container][columns[1]]
        self._data[output_container][name] = \
        self._data[output_container][name] / denominator
        
    def absolute_percentage_difference(self, name, columns, input_container, output_container):
        '''
        @name: str, the new column name where output of function is 
        @columns: list of column names, where order matters to execution of operator
        - ABS(X-Y)
        '''
        self.percentage_difference(name, columns, input_container, output_container)
        self._data[output_container][name] = abs(self._data[output_container][name])

    

#==============================================================================
# 
#==============================================================================
'''
import pandas as pd

hdf = pd.HDFStore('testing1.h5')



d=pd.read_csv('C:/MFU/Data/20180403/ALL_CRISKREPMFU_OtherBBExposure_20180403_D_001.zip',
              sep="|",skipfooter=1,skiprows=1)

hdf.append('d1',d.append(d).append(d).append(d))
hdf['d1'] = d
hdf['d1']

hdf.remove('d1')

hdf.get('d1')

print(hdf)

hdf.close()

 
del hdf
print(hdf)

'''

@util.py

import pandas as pd
# use lazy evaluation
#import dask.dataframe as pd
import time
import re
import os, sys, psutil
import zipfile

import string
from string import Template
import numpy as np
from proj_query_engine.UDF import *

#==============================================================================
# config templates
#==============================================================================

class config_file(object):
    """ initialising default kwargs of read_csv, read_excel """
    def __init__(self):
        pass

class config_csv(config_file):
    def __init__(self, filepath, sep=",", header=0, 
                 skiprows=0, skipfooter=0, dummycol=None, append=None, \
                 encoding='utf-8', dtype=None, names=None, \
                 usecols = None, low_memory=True, na_values = None):
        self.filepath_or_buffer = filepath
        self.encoding = encoding #'iso-8859-1'
        self.sep = sep
        self.header = header
        self.skipfooter = skipfooter
        self.skiprows = skiprows
        self.dtype = dtype
        self.usecols = usecols
        self.names = names
        self.low_memory = low_memory
        self.na_values = na_values
        self.dummycol = dummycol
        self.append = append
        
class config_excel(config_file):
    def __init__(self, filepath, sheet_name, header=0, 
                 skiprows=0, skipfooter = 0, dummycol=None, append=None, \
                 encoding='iso-8859-1', dtype=None, names=None):
        self.io = filepath
        self.encoding = encoding
        self.sheet_name = sheet_name
        self.skiprows = skiprows
        self.header = header
        self.skip_footer = skipfooter
        self.dtype = dtype
        self.names = names
        self.dummycol = dummycol
        self.append = append


#==============================================================================
# decorators
#==============================================================================

def timeit(method):
    """
    method decorator to time completion of a function
    """
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        if 'log_time' in kw:
            name = kw.get('log_name', method.__name__.upper())
            kw['log_time'][name] = int((te - ts) * 1000)
        else:
            print( '%r  %2.2f ms' %  (method.__name__, (te - ts) * 1000))
        return result
    return timed

def dynamic_arg(config):
    """ allow passing of **kwargs into a function that needs it """
    def dynamic_arg_f(f):
        def f_decorator(*args, **kwargs):
            kwargs.update(config.__dict__)
            return f(*args, **kwargs)
        return f_decorator
    return dynamic_arg_f

#@dynamic_arg(csv_config)
#def read_csv_with_config(filepath_or_buffer, **kwargs):
#    return pd.read_csv(filepath_or_buffer=filepath_or_buffer, **kwargs)
#
#@dynamic_arg(excel_config)
#def read_excel_with_config(io, **kwargs):
#    return pd.read_excel(io=io, **kwargs)


#==============================================================================
# for future uses
#==============================================================================

def sort_column(df, colname, ascending=True):
    '''
    @colname: str or list (composite sort in order)
    sort values in any column besides index
    '''
    print("Sorting frame by column " + str(colname))
    
    if isinstance(colname, str):
        if df.index.name == colname:
            return df.sort_index(ascending=ascending)
        else:
            return df.sort_values(colname, ascending=ascending)
            
    elif isinstance(colname, list):
        temp = df
        for col in colname:
            temp = sort_column(temp, col, ascending=ascending)
        return temp
    else:
        print("Invalid type for colname to sort")
    

def sort_header(df, order=None):
    """
    @order: str or list
    Example: order = ['count','sum'] groups all column headers that contains count 
    or None to be sorted alphabetically
    """
    if isinstance(order, str): order = [order]
    newcols = []
    oldcols = list(df.columns.values)
    if isinstance(order,list):            
        for col in order:
            for old_col in oldcols:
                if str(old_col).find(col) != -1:
                    newcols.append(old_col)
    else:
        print("Invalid order given for sort_header")
        return df

    notfoundcols = [x for x in oldcols if x not in newcols]
    return df.loc[:, newcols + notfoundcols]


#==============================================================================
# functions
#==============================================================================

def has_extension_str(filename:str, extension:str=None):
    if extension:
        if filename.endswith(extension):
            return filename
        else:
            return None

def has_extension_list(filename: list, extension:str=None):    
    if extension:
        return [file if file.endswith(extension) else None for file in filename]

def has_extension(filename, extension=None):
    """
    check for file extension, if True, return (bool, extension)
    """
    # allow extension to filename type
    f_map = {
            str : has_extension_str,
            list : has_extension_list
            }
    try:
        if isinstance(extension, str):
            return ( f_map[type(filename)](filename, extension), extension)
        elif isinstance(extension, list):
            for ext in extension:
                boo = f_map[type(filename)](filename, ext)
                print(boo)
                if bool(boo):
                    return (boo, ext)
            return (None, None)
        else:
            pass
    except:
        raise TypeError("Filename either str or list")

def unzip(filepath, dest, inplace=False):
    """ extract all files from .zip and returns filenames as list """
    suffix = filepath[:filepath.rfind("/")+1]
    if has_extension(filepath, ".zip"):
        print("Unzipping " + filepath)
        zip_ref = zipfile.ZipFile(filepath, mode='r') # create zipfile object            
        zip_ref.extractall(dest) # extract file to dir
        zip_ref.close() # close file
        if inplace: 
            os.remove(filepath) # delete zipped file
    return [suffix + f.filename for f in zip_ref.filelist]


def append_dummycol(df, dummycol: dict):
    """
    append dummy col to pandas.dataframe
    """
    assert isinstance(dummycol, dict)
    for key, value in dummycol.items():
        df[key] = value
    return df

def reader(**kwargs):
    """
    Supports csv, xls, xlsx, xlsb input path
    filepaths use ...\ not /
    """
    if 'io' in kwargs.keys(): 
        filepath = kwargs.pop('io')
    elif 'filepath_or_buffer' in kwargs.keys(): 
        filepath = kwargs.pop('filepath_or_buffer')
    else:
        print("Unsupported input filepath found!")
    
    # unzip and followup to read unzip files
    if bool(has_extension(filepath,'.zip')[0]):
        zippaths = unzip(filepath, filepath[ : filepath.rfind("/")])
        print("Unzip files are: " + str(zippaths))
        suffix = filepath[ : filepath.rfind(".")]
        if suffix+".xlsx" in zippaths:
            return reader(io = suffix+".xlsx", **kwargs)
        elif suffix+".xls" in zippaths:
            return reader(io = suffix+".xls", **kwargs)            
        elif suffix+".xlb" in zippaths:
            return reader(io = suffix+".xlb", **kwargs)
        elif suffix+".csv" in zippaths:
            return reader(io = suffix+".csv", **kwargs)
        else:
            print("Unsupported file extension found!")
            return
        
    elif bool(has_extension(filepath,['.xlsx','.xls', 'xlb'])[0]):
        return pd.read_excel(io=filepath, **kwargs)
    elif bool(has_extension(filepath,['.csv'])[0]):
        return pd.read_csv(filepath_or_buffer = filepath, **kwargs)

    else:
        print("invalid csv or excel filetype")
        return


def function_name(f):
    ''' f.__name__ '''
    aggf = str(f)
    aggf = aggf.lstrip('<function').lstrip(" ")
    aggf = aggf[:aggf.find(" ")]
    return aggf

#def pretty_column_names(colnames, val):
#    """ """
#    words_to_include_value = ['sum', 'stdev']
#    colnames = [x + " " + val if any(word in x for word in words_to_include_value) 
#        else x for x in colnames]
#    return colnames

def kw_arguments(f):
    import inspect
    sig = inspect.signature(f)
    return [p.name for p in sig.parameters.values() 
            if p.kind == p.POSITIONAL_OR_KEYWORD]
        
def relevant_kw(f, kw):
    '''
    Separate what can be **kwargs that's passable into f
    '''
    kw_default = kw_arguments(f)
    if isinstance(kw, config_file):
        _dict = kw.__dict__
        _kw = list(kw.__dict__.keys())
    elif isinstance(kw, dict):
        _dict = kw
        _kw = list(kw.keys())
    else:
        print("Invalid type")

    d, extra_kwargs = {}, {}
    for w in _kw:
        if w in kw_default:
            d.update({w:_dict[w]})
        else:
            extra_kwargs.update({w:_dict[w]})

    return d, extra_kwargs

def prettify_colnames_from_R(df):
    '''
    fix column names <----- R outputs
    '''
    cv=[x.strip('.') for x in df.columns.values]
    cv=[x.replace("..."," ") for x in cv]
    cv=[x.replace(".."," ") for x in cv]
    cv=[x.replace("."," ") for x in cv]
    df = df.rename(columns = dict(zip(list(df.columns.values), cv)))
    print(list(df.columns.values))
    return df

def memory_usage(x):
    ''' returns memoery usage of each container in a dictionary '''
    if isinstance(x, dict):
        for k,v in x.items():         
            print( str(k) + " currently using " + 
                  str(sys.getsizeof(v) / float(2 ** 20)) + " Mb")
    elif isinstance(x, list):
            print(x + "List currently using " + 
                  str(sys.getsizeof(x) / float(2 ** 20)) + " Mb")
    elif isinstance(x, pd.core.frame.DataFrame):
        print("currently using " + 
              str(sys.getsizeof(x) / float(2 ** 20)) + " Mb")
    else:
        print("Memory too small to print!")

def python_memory_usage():
    process = psutil.Process(os.getpid())
    print("Python currently using " + 
          str(process.memory_full_info().rss / float(2 ** 20)) + " Mb")

def str_to_numeric(s):
    ''' use for parsing formulas '''
    return float(re.sub(r"^\s+|\s+$", "", s))

def clean_filepath(x):
    x = str(x)
    x = x.replace(":","_")
    x = x.replace(".","_")
    x = x.replace(" ","_")    
    return x


def check_methods(query, job:str):
    '''Ensure no undefined methods in query/calculate '''
    if job == "query":
        defined_methods = ['crosstab', 'filter', 'select', 'deselect', 'groupby', 
                           'startswith', 'endswith', 'contains', 'append', 
                           'top', 'bottom']
    if job == "calculate":
        defined_methods = ['difference', 'absolute_difference',
                           'percentage_difference','absolute_percentage_difference',
                           'summation']
    
    keys_to_remove = []
    for k in query.keys():
        if k not in defined_methods:
            keys_to_remove.append(k)
    for k in keys_to_remove: query.pop(k)


#==============================================================================
# Dictionary interpreter
#==============================================================================

class Template(string.Template):
    ''' override string.Template defaults '''
    delimiter = '@'
    idpattern = r'[a-z][_a-z0-9]*'

#https://stackoverflow.com/questions/12507206/python-recommended-way-to-walk-complex-dictionary-structures-imported-from-json
def walk_for_functions(d, path = [], paths_to_chg = {}):
    '''
    traverse all paths in dict and returns all paths that need its values evaluated
    '''
    for k,v in d.items():
        if isinstance(v, str):
            try:
                v1 = eval(v)
                if not isinstance(v1,int):
                    if str(v1).startswith('<') and str(v1).endswith('>'):
                        path.append(k)
                        print("{} <--- {}".format("|".join( 
                                [str(x) for x in path] ), str(v)))
                        
                        nesting = ''
                        for p in path:
                            if isinstance(p, int): nesting += "[" + str(p) + "]"
                            else: nesting += "['" + p + "']"
                        paths_to_chg[nesting] = v
                        path.pop()
                    
                    #for "None" --> --> None
                    if v1 is None:
                        path.append(k)
                        print("{} <--- {}".format("|".join( 
                                [str(x) for x in path] ), str(v)))
                        
                        
                        print(path)
                        
                        
                        nesting = ''
                        for p in path:
                            if isinstance(p, int): nesting += "[" + str(p) + "]"
                            else: nesting += "['" + p + "']"
                        paths_to_chg[nesting] = None
                        path.pop()
                    
            except NameError:
                pass
            
            except SyntaxError:
                pass
        
        elif isinstance(v, list):
            for i in range(len(v)):
                try:
                    print(type(v[i]))
                    print(v[i])
                    
                    if isinstance(v[i], dict):
                        path.append( k )
                        path.append( i )
                        print("{} <--- {}".format("|".join( 
                                [str(x) for x in path] ), str(v[i])))
                        
                        walk_for_functions(v[i])
                        
                        path.pop()
                        path.pop()
                        
                    elif not isinstance(v[i],int):
                        v1 = eval(v[i])
                        if not isinstance(v1,int):
                            if str(v1).startswith('<') and str(v1).endswith('>'):
                                path.append( k )
                                path.append( i )
                                print("{} <--- {}".format("|".join( [str(x) for x in path] ), str(v[i])))

                                nesting = ''
                                for p in path:
                                    if isinstance(p, int): nesting += "[" + str(p) + "]"
                                    else: nesting += "['" + p + "']"
                                paths_to_chg[nesting] = v[i]
                                
                                path.pop()
                                path.pop()
                                
                    else: 
                        print("Error in parsing values in list")
                        
                except NameError:
                    pass
                
                except SyntaxError:
                    pass

        
        elif v == {}:
            pass
            #path.append(k)
            #path.pop()
            
        elif isinstance(v, dict):
            path.append(k)
            walk_for_functions(v)
            path.pop()
            
        elif isinstance(v, int):
            pass
        
        else:
            path = [str(x) for x in path]
            print("###Type {} not recognized: {}.{}={}".format(
                    type(v), "|".join(path), str(k), str(v) ))

    return paths_to_chg


def substitute_templates(d, kw, obj=string.Template, path = [], paths_to_chg = {}):
    '''
    substitute template patterns
    '''
    for k,v in d.items():
        print(k , "---->" , v)
        if isinstance(v, obj):
            
            # $cob is x[1]    ${cob} is x[2]
            keys = list(set([ x[1]+x[2] for x in 
                             Template.pattern.findall(v.template)]))
            arg = ''
            print(keys)
            for key in keys:
                arg += key + "=kw['" + key + "'], "
            if len(arg) != 0: arg = arg.rstrip(', ')

            print("\n")
            print("v.substitute(" + arg + ")")
            
            v = eval(r"v.substitute(" + arg + ")")
            
            print(v)
            
            path.append(k)
            print("{} <--- {}".format("|".join( 
                    [str(x) for x in path] ), str(v)))
            
            nesting = ''
            for p in path: 
                if isinstance(p, int): nesting += "[" + str(p) + "]"
                else: nesting += "['" + p + "']"
            paths_to_chg[nesting] = v
            path.pop()
            

        elif isinstance(v, list):
            for i in range(len(v)):
                
                if isinstance(v[i], dict):
                    path.append( k )
                    path.append( i )
 
                    substitute_templates(d=v[i], kw=kw, obj=obj)

                    path.pop()
                    path.pop()
                
                elif isinstance(v[i], obj):
                    
                    keys = list(set([ x[1] for x in Template.pattern.findall(v[i].template)]))
                    arg = ''
                    for key in keys:
                        arg += key + "=kw['" + key + "'], "
                    if len(arg) != 0: arg = arg.rstrip(', ')
                    
                    print("\n")
                    print(eval("v[i].template"))
                    print("v[i].substitute(" + arg + ")")
                    
                    v[i] = eval(r"v[i].substitute(" + arg + ")")

                    path.append(k)
                    path.append( i )
                    print("{} <--- {}".format("|".join( 
                            [str(x) for x in path] ), str(v[i])))
                    
                    nesting = ''
                    for p in path: 
                        if isinstance(p, int): nesting += "[" + str(p) + "]"
                        else: nesting += "['" + p + "']"
            
                    paths_to_chg[nesting] = v[i]
                    path.pop()                    
                    path.pop()
                    
                else:
                    print("List element type not recognised!")
        
        elif v == {}:
            pass
            #path.append(k)
            #path.pop()
            
        elif isinstance(v, dict):
            path.append(k)
            substitute_templates(d=v, kw=kw, obj=obj)
            path.pop()

        elif isinstance(v, str):
            pass
                    
        elif isinstance(v, int):
            pass
        
        else:
            path = [str(x) for x in path]
            print("###Type {} not recognized: {}.{}={}".format(
                    type(v), "|".join(path),k, v))

    return paths_to_chg


def parse_templates(dictionary, keywords):
    """ parse and substitute all templates in a dictionary from YAML/JSON configuration """
    paths_to_chg = substitute_templates(d=dictionary, kw=keywords, obj=Template)
    for k,v in paths_to_chg.items():
        #print(k,v)
        print( "dictionary" + k + ' = "' + v + '"')
        exec("dictionary" + k + ' = "' + v + '"',None,locals())

    return dictionary

# https://stackoverflow.com/questions/2220699/whats-the-difference-between-eval-exec-and-compile-in-python
# https://www.saltycrane.com/blog/2008/01/python-variable-scope-notes/
def eval_dict_values(dictionary):
    """ evaluate all values in a dictionary """
    paths_to_chg = walk_for_functions(dictionary)
    
    for k,v in paths_to_chg.items():
        #print(k,v)
        print( "dictionary" + k + ' = eval("' + str(v) + '")')
        exec("dictionary" + k + ' = eval("' + str(v) + '")',None,locals())
    return dictionary

@UDF.py


#==============================================================================
# UDER DEFINED FUNCTIONS - its operation on pandas.Series
# Uses: query_engine
#==============================================================================

import functools
import numpy as np

def count(series):
    return len(series)

def sum_millionth(series):
       return functools.reduce(lambda x, y: x/1000000 + y/1000000, series)

def count_nulls(series):
    return len(series) - series.count()

def ran(series):
    return max(series) - min(series)

@main.py

#==============================================================================
# JOB: General Purpose query engine on local file systems
#==============================================================================
import sys
import yaml
import re
from datetime import datetime
from proj_query_engine.core import (query_engine, 
                                      config_excel, 
                                      config_csv)

from proj_query_engine.util import *

import gc
gc.enable()
#gc.set_debug(gc.DEBUG_LEAK)

#import py_excel
#from importlib import reload
#reload(query_engine)


#inputs
ETL_config = sys.argv[1] # k-v .YAML path
dest_path = sys.argv[2] # dest path
inputs = sys.argv[3] # for Template substitution
print(sys.argv)

#stdout_filename = "stdout_" + clean_filepath(datetime.now()) + ".txt"
#stderr_filename = "stderr " + clean_filepath(datetime.now()) + ".txt"
#sys.stdout = open("C:/MFU/log/" + stdout_filename, "w")
#sys.stderr = open("C:/MFU/log/" + stderr_filename, "w")


inputs = [re.sub(r'\s+', '', x) for x in inputs.split(sep='@')][1:]
keywords = {}
for i in inputs:
    kv = i.split('=')
    keywords[kv[0]] = kv[1]

# CoB is yyyymmdd
if 'cob' in keywords.keys():
    cob = datetime.strptime(keywords['cob'], "%Y%m%d")
    keywords['yy'] = datetime.strftime(cob, "%y")
    keywords['yyyy'] = datetime.strftime(cob, "%Y")
    keywords['mm'] = datetime.strftime(cob, "%m")
    keywords['mmm'] = datetime.strftime(cob, "%b")
    keywords['dd'] = datetime.strftime(cob, "%d")


#==============================================================================
# Parsing config.YAML
#==============================================================================

print("Parsing YAML!")

#load templates for pivots and summary statistics and formatting
with open(ETL_config) as jdata:
    try:
        report = yaml.load(jdata) # np.sum will not be eval
    except Exception as e: 
        print(e)
        
# parse YAML inputs to evaluate objects and functions
report = eval_dict_values(report)
# parse string.Templates
report = parse_templates(report, keywords)
print("Parsed YAML!")

report


cfg_csv , cfg_excel = None, None
if '+extraction' in report.keys():
    if len(report['+extraction'])>0:
        cfg_csv, cfg_excel = [], []
        for config in report['+extraction']:
            for config_type, config_parameters in config.items(): 
                if config_type.find("config_csv") != -1:
                    cfg_csv.append(config_parameters)
                if config_type.find("config_excel") != -1:
                    cfg_excel.append(config_parameters)

_cfg_csv_list = [config_csv(**x) for x in cfg_csv]
_cfg_excel_list = [config_excel(**x) for x in cfg_excel]

print("Finish [+extraction] input configuration!")

# init query engine --> input paths from each file from config.YAML
x = query_engine(dest_path = dest_path, 
                 cfg_csv_list = _cfg_csv_list, 
                 cfg_excel_list = _cfg_excel_list,
                 checkMemory = True)
#sys.getsizeof(x)


print("Starting [+transformation] queries!")

# dynamic config for individual input filepath --> filepath from YAML config
if '+transformation' in report.keys():
    transformation = report['+transformation']
    # calling queries 
    for item in transformation:
        item_type = None
        # nested query to provde additional layer of data flow control
        if list(item.keys())[0] == 'query':
            print("Processing query... ")
            query = item['query']
            item_type = 'query'
        elif list(item.keys())[0] == 'calculate':
            print("Processing calculate... ")
            query = item['calculate']
            item_type = 'calculate'
        elif len(item.keys())>1:
            print("calculate / query only has 1 key")
            break
        else:
            print(item.keys())
            print("Only accepts list of 'query'... ")
            break

        # get input, output container
        input_container = query.pop('data')
        output_container = query.pop('output')

        if item_type == 'query': check_methods(query, job="query")
        if item_type == 'calculate': check_methods(query, job="calculate")


        # create new container if diverging data flow path
        if not output_container in x._data.keys():    
            x._data.update({output_container : None})
        
        # execute query in order . Note: dict.keys() are not auto sorted
        for method, kwargs in query.items():
            if isinstance(kwargs, dict):
                # dict => **kwargs
                kwargs.update(dict(input_container = input_container))
                # subsequent queries will work inside output_container
                kwargs.update(dict(output_container = output_container))
                print("Processing on container: " + input_container)
                print("Performing " + method + " with parameters: ")
                print(kwargs)
                eval('x.' + method + '(**kwargs)')
                print("Output to container: " + output_container)
                
            elif isinstance(kwargs, str) or isinstance(kwargs, list):
                non_dict_kwargs = dict(input_container=input_container,
                                       output_container=output_container)
                eval('x.' + method + '(kwargs, **non_dict_kwargs)')
            
            else: 
                print("Invalid type for transformation method's kwargs")
            
            # subsequent query to work from output_container
            input_container = output_container


print("Finish [+transformation] queries!")

# temporary
x.closewb()
x.check_memory()




