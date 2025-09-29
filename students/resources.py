from import_export import resources, fields
from students.models import Student

class AppBModelResource(resources.ModelResource):
    # 1. Map 'student_detail' from your CSV to 'usn' in your model
    usn = fields.Field(attribute='usn', column_name='student_detail')
    standard = fields.Field(attribute='standard', column_name='current_class')
    form_teacher = fields.Field(attribute='form_teacher', column_name='class_teacher')

    # 2. Map other fields from your source CSV to your destination model
    #    Adjust 'column_name' to match your actual CSV headers from the source model.
    # new_name = fields.Field(attribute='new_name', column_name='original_name') # Assuming 'original_name' in source CSV
    # product_description = fields.Field(attribute='product_description', column_name='description') # Assuming 'description' in source CSV
    # current_status = fields.Field(attribute='current_status', column_name='old_status') # Assuming 'old_status' in source CSV

    def before_import_row(self, row, **kwargs):
        """
        This method is called for each row *before* it's imported.
        Use it for:
        - Setting default values for new fields in AppBModel not present in CSV.
        - More complex data transformations.
        - Generating additional rows (though this requires pre-processing the CSV).
        """
        # Apply default values for fields not in your source CSV
        # if 'category' not in row or not row['category']:
        #     row['category'] = 'Default Category'
        # if 'quantity' not in row or not row['quantity']:
        #     row['quantity'] = 1

        if 'blood_group' not in row or not row['blood_group']:
             row['blood_group'] = 'select'
        if 'genotype' not in row or not row['genotype']:
             row['genotype'] = 'select'
        if 'health_remark' not in row or not row['health_remark']:
             row['health_remark'] = 'enter health detail'

        if 'hostel_name' not in row or not row['hostel_name']:
             row['hostel_name'] = 1
       
        # Example: Transform status if needed
        # status_map = {'active': 'ENABLED', 'inactive': 'DISABLED'}
        # source_status = row.get('old_status')
        # if source_status in status_map:
        #     row['current_status'] = status_map[source_status]
        # else:
        #     row['current_status'] = 'UNKNOWN'

        # NO NEED to explicitly generate USN here IF 'student_detail'
        # in your CSV already provides a unique value for USN.
        # If 'student_detail' might be empty or not unique, then you'd add
        # generation/validation logic here.

    class Meta:
        model = Student
        # Crucial: Tell django-import-export that 'usn' is the field to use
        # for identifying existing records (if any) and as the primary key.
        import_id_fields = ['usn']

        # Specify all fields you want to import/export.
        # Ensure 'usn' is listed here.
        # fields = ('usn', 'standard', 'form_teacher', )
        fields = '__all__'

        # Ignore the default 'id' field from the source CSV, as AppBModel doesn't have it.
        # This will prevent the "KeyError: 'id'" error.
        # You don't need to explicitly exclude 'id' if you define 'fields',
        # but it reinforces the intention.
        exclude = ('id',) # Explicitly exclude if 'fields' isn't used to whitelist

        skip_unchanged = True
        report_skipped = True