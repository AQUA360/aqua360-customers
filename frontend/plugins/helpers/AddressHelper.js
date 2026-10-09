export default defineNuxtPlugin(nuxtApp => {
  const provideName = 'AddressHelper';

  const s = (val) => val ?? '';

  const getNumberString = (street_number) => {
    let number_display = '';
    if (street_number.number == null && street_number.number_end == null && street_number.number_suffix == null) {
      street_number.number_type = {
        type: 'SN'
      }
    }
    if (street_number.number_type?.type == 'N')
      number_display = s(street_number.number);
    else if (street_number.number_type?.type == 'SN')
      number_display = 'S/N';
    else if (street_number.number_type?.type == 'R')
      number_display = `${s(street_number.number)}${s(street_number.number_suffix)}-${s(street_number.number_end)}${s(street_number.number_end_suffix)}`;
    else if (street_number.number_type?.type == 'S') {
      if (street_number.number) {
        if (street_number.number_end)
          number_display = `${s(street_number.number)}-${s(street_number.number_end)} ${s(street_number.number_suffix)}`;
        else
          number_display = `${s(street_number.number)} ${s(street_number.number_suffix)}`;
      }
      else
        number_display = s(street_number.number_suffix);
    }
    else {
      number_display = `${s(street_number.number)} ${s(street_number.number_suffix)} - ${s(street_number.number_end)} ${s(street_number.number_end_suffix)}`;
    }

    return String(number_display)
  }

  const getStreetString = (data) => {
    let text = '';

    if (data.address_street) {
      text += s(data.address_street.type_abbreviation) + '. ' + s(data.address_street.name);
    }

    if (data.street) {
      text += s(data.street.type_abbreviation) + '. ' + s(data.street.name);
    }

    return String(text);
  }

  const getAddressString = (data) => {
    try {
      if (data && data.address_street) {
        let text = '';
        text += getStreetString(data);
        if (data.address_street_number) {
          text += ', ' + getNumberString(data.address_street_number);
        }
        if (data.address_city || data.address_postal_code) {
          text += ' - ';
        }
        if (data.address_postal_code) {
          text += s(data.address_postal_code.code) + ' ';
        }
        if (data.address_city) {
          text += s(data.address_city.name);
        }
        return text;
      } else {
        return 'Sense adreça';
      }
    }
    catch (error) {
      console.error(error);
      return 'Sense adreça';
    }
  }

  const helperService = {
    getNumberString,
    getStreetString,
    getAddressString
  };

  nuxtApp.provide(provideName, helperService);
});