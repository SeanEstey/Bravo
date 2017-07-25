/* etapestry.js */


function getPhone(type, acct) {

    var phones = acct['phones'];

    if(!phones)
        return null;

    for(var i=0; i<phones.length; i++) {
        if(phones[i]['type'] == type)
            return phones[i]['number'];
    }

    return null;
}

function getDV(name, acct) {

    var multis = [];
    var isMulti = false;

    var dv = acct['accountDefinedValues'];

    if(!dv)
        return null;

    for(var i=0; i<dv.length; i++) {

        if(dv[i]['fieldName'] != name)
            continue

        if(dv[i]['displayType'] == 2) {
            isMulti = true;
            multis.push(dv[i]['value']);
            continue;
        }

        if(dv[i]['dataType'] == 1) {
            var parts = dv[i]['value'].split('/');
            return new Date(format("%s/%s/%s",parts[1],parts[0],parts[2]));
        }

        return dv[i]['value'];
    }

    return isMulti ? multis.join(", ") : null;
}
