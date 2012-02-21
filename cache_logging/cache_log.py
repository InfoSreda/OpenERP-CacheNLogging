# -*- coding: utf-8 -*-

##############################################################################
#
#    Authors: Boris Timokhin, Peter A. Kurishev
#    Copyright (C) 2011 - 2012 by InfoSreda LLC
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields, osv


class cache_log(osv.osv):
    _name = "cache.log"
    _description = "Log changes for model under cache"
    #_auto = False

    _columns = dict(
        model_id=fields.many2one('ir.model', 'Model', required=True),
        model_name=fields.related('model_id', 'model', string='Model name',
                                  type='char'),
        per_user=fields.boolean('Per user'),
        without_data=fields.boolean('Without data'),
        last_modified=fields.datetime('Last modified', readonly=True, select=1),
        model_table=fields.char('Table name', size=64)
        )

    def add_rules_trigger(self, cr):
        # TODO: change_rules trigger
        #cr.execute('')
        pass

    def add_module_trigger(self, cr):
        # if module change need reset cache becouse may be side effects
        cr.execute('CREATE OR REPLACE FUNCTION trigger_modules_change_cache_reset ()\n' \
                   ' RETURNS trigger AS \'\n' \
                   ' BEGIN\n' \
                   '  update cache_log set last_modified = now();\n' \
                   '  return NEW;\n' \
                   ' END;\n' 
                   '\' LANGUAGE  plpgsql;\n'
                   )
        cr.execute('DROP TRIGGER IF EXISTS modules_change_reset_cache \n'\
                   '  ON ir_module_module;')
        cr.execute('CREATE TRIGGER modules_change_reset_cache \n' \
                   ' AFTER INSERT OR UPDATE ON ir_module_module FOR EACH ROW\n'\
                   ' EXECUTE PROCEDURE trigger_modules_change_cache_reset()')

    def add_change_trigger_func(self, cr):
        cr.execute('CREATE OR REPLACE FUNCTION trigger_model_change_cache_reset ()\n' \
                   ' RETURNS trigger AS \'\n' \
                   ' BEGIN \n' \
                   '  update cache_log set last_modified = now() \n' \
                   '    where model_table = TG_RELNAME; \n'\
                   '  return NEW; \n' \
                   ' END;\n' 
                   '\' LANGUAGE  plpgsql;\n'
                   )

    def _auto_init(self, cr, *args, **kwargs):
        super(cache_log, self)._auto_init(cr, *args, **kwargs)
        self.add_rules_trigger(cr)
        self.add_module_trigger(cr)
        self.add_change_trigger_func(cr)

    def _add_trigger(self, cr, model_table):
        # create trigger funcion
        cr.execute('DROP TRIGGER IF EXISTS cache_log_for_%s \n' \
                   '  ON %s;\n' % (model_table, model_table))

        cr.execute(
            'CREATE TRIGGER cache_log_for_%s \n' \
            ' AFTER INSERT OR UPDATE ON %s FOR EACH ROW \n' \
            ' EXECUTE PROCEDURE trigger_model_change_cache_reset()\n' % \
            (model_table, model_table)
            )

    def _del_trigger(self, cr, model_table):
        cr.execute('DROP TRIGGER IF EXISTS cache_reset_for_%s \n' \
                   '  ON %s' % (model_table, model_table))

    def create(self, cr, uid, values, context=None):
        model_name = self.pool.get('ir.model').read(cr, uid,
                                                    [values['model_id']],
                                 ['model'], context=context)[0]['model']
        values['model_table'] = self.pool.get(model_name)._table

        res = super(cache_log, self).create(cr, uid, values, context)
        self._add_trigger(cr, values['model_table'])
        return res

    def write(self, cr, uid, ids, values, context=None):
        res = super(cache_log, self).write(cr, uid, ids, values,
                                           context=context)
        for record in self.browse(cr, uid, ids, context):
            self._add_trigger(cr, record.model_table)
        return res        

    def unlink(self, cr, uid, ids, context=None):
        model_tables = []
        for record in self.browse(cr, uid, ids, context):
            model_tables.append(record.model_table)

        res = super(cache_log, self).unlink(cr, uid, ids, context)
        for model_table in model_tables:
            if model_table:
                self._del_trigger(cr, model_table)
        return res

cache_log()
