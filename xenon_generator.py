import itertools
import pprint
import sys

from base_datatypes import *
from commands import recursiveSelect
import xenon_exceptions as xe

class SweepableView(XenonObj):
  """ An overlay for Sweepable objects.

  Sweepable objects describe a range of values that their attributes can take
  on.  A SweepableView is an instantiation of one possible combination of those
  values that does not modify any state of the wrapped Sweepable object. When
  fully generated, a SweepableView can be dumped in JSON form and reformatted
  by a backend for some target output.
  """
  def __init__(self, sweepable_obj):
    super(SweepableView, self).__init__()
    # Wrap the sweepable object so we can access its range.
    self.sweepable = sweepable_obj
    # A list of attributes that we've copied from sweepable_obj.
    self.attrs = []
    # Copy the sweepable attributes from sweepable_obj.
    for name, value in self.sweepable.getSweepableParamsAndValues().iteritems():
      setattr(self, name, value)
      self.attrs.append(name)
    # Recursively copy all Sweepable children from sweepable_obj.
    for child_name, child in self.sweepable.iterattritems(objtype=Sweepable):
      setattr(self, child_name, SweepableView(child))
      self.attrs.append(child_name)

  def dump(self):
    dictified = self.dictify()
    printer = pprint.PrettyPrinter(indent=2)
    printer.pprint(dictified)

  def dictify(self):
    key = str(self)
    children = {}
    for attr_name in self.attrs:
      attr_value = getattr(self, attr_name)
      if isinstance(attr_value, SweepableView):
        children[attr_name] = attr_value.dictify()
      else:
        children[attr_name] = attr_value
    return children

  def __repr__(self):
    return "{0}({1}(\"{2}\"))".format(
        self.__class__.__name__, self.sweepable.__class__.__name__, self.sweepable.name)

class XenonGenerator(XenonObj):
  def __init__(self, configured_sweep):
    super(XenonGenerator, self).__init__()
    self.sweep = configured_sweep

  def generate(self):
    """ Generate all configurations of this sweep. """
    param_range_len = self.discoverSweptParameters()
    indices_list = []
    id_list = []
    for param_id, range_len in param_range_len.iteritems():
      id_list.append(param_id)
      indices_list.append(range(0, range_len))
    indices_list = tuple(indices_list)

    # index_combinations is a generator of tuples, where the ith value is the
    # index of the parameter range with parameter id id_list[i].
    index_combinations = itertools.product(*indices_list)
    top_view = SweepableView(self.sweep)
    for indices in index_combinations:
      self.applySweepParamValues(top_view, id_list, indices)
      top_view.dump()

  def applySweepParamValues(self, root_view, ids, indices):
    for param_id, param_idx in zip(ids, indices):
      if param_id in root_view.sweepable.sweep_params_range:
        param_value = root_view.sweepable.sweep_params_range[param_id][param_idx]
        param_name = root_view.sweepable.getParamName(param_id)
        setattr(root_view, param_name, param_value)

    for child_view in root_view.iterattrvalues(objtype=SweepableView):
      self.applySweepParamValues(child_view, ids, indices)

  def discoverSweptParameters(self):
    """ Return a list of all swept Param objects.

    TODO: Fix documentation.
    """
    # Get all the sweepable objects.
    all_sweepable = recursiveSelect(self.sweep, objtype=Sweepable)
    range_len = {}
    for sweepable in all_sweepable:
      if not hasattr(sweepable, "sweep_params_range"):
        continue
      for param_id, param_range in sweepable.sweep_params_range.iteritems():
        if param_id in range_len and range_len[param_id] != len(param_range):
            param_name = sweepable.getParamName(param_id)
            raise xe.XenonMismatchingRangeError(
                param_name, len(param_range), range_len[param_id])
        else:
          range_len[param_id] = len(param_range)

    return range_len