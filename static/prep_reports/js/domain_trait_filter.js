// (function($) {

//     function updateTrait(row) {

//         const domain = row.find(
//             'select[id$="-domain"]'
//         ).val();

//         const trait = row.find(
//             'select[id$="-trait_name"]'
//         );

//         if (!trait.length) return;

//         const current = trait.val();

//         trait.empty();

//         trait.append(
//             $('<option>', {
//                 value: '',
//                 text: '---------'
//             })
//         );

//         if (
//             !domain ||
//             !window.prepDomainTraitMap
//         ) {
//             return;
//         }

//         const traits =
//             window.prepDomainTraitMap[
//                 domain
//             ] || [];

//         traits.forEach(function(item) {

//             trait.append(
//                 $('<option>', {
//                     value: item.value,
//                     text: item.label,
//                     selected:
//                         item.value === current
//                 })
//             );

//         });
//     }

//     function bindRow(row) {

//         row.on(
//             'change',
//             'select[id$="-domain"]',
//             function() {
//                 updateTrait(row);
//             }
//         );

//         updateTrait(row);
//     }

//     $(document).ready(function() {

//         $('tr.form-row').each(function() {
//             bindRow($(this));
//         });

//         $(document).on(
//             'formset:added',
//             function(event, row) {
//                 bindRow($(row));
//             }
//         );

//     });

// })(django.jQuery);

(function($) {

    function updateTrait(row) {

        let domain = row.find(
            'select[id$="-domain"]'
        ).val();

        let trait = row.find(
            'select[id$="-trait_name"]'
        );

        if (!trait.length) return;

        let current = trait.val();

        trait.empty();

        trait.append(
            $('<option>')
                .val('')
                .text('---------')
        );

        if (
            !domain ||
            !window.prepDomainTraitMap
        ) {
            return;
        }

        let traits =
            window.prepDomainTraitMap[
                domain
            ] || [];

        traits.forEach(function(item) {

            trait.append(
                $('<option>')
                    .val(item.value)
                    .text(item.label)
            );

        });

        if (current) {
            trait.val(current);
        }
    }

    function bindRow(row) {

        row.on(
            'change',
            'select[id$="-domain"]',
            function() {
                updateTrait(row);
            }
        );

        updateTrait(row);
    }

    $(document).ready(function() {

        $('tr.form-row').each(function() {
            bindRow($(this));
        });

        $(document).on(
            'formset:added',
            function(
                event,
                row
            ) {
                bindRow($(row));
            }
        );

    });

})(django.jQuery);