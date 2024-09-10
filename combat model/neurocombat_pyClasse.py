# -*- coding: utf-8 -*-
"""confounder_correction_classes_updated_with_modmean.ipynb

Automatically generated by Colaboratory.

"""

#Drive
#from google.colab import drive
#drive.mount('/content/drive')


from sklearn.utils.validation import check_X_y, check_array, check_is_fitted
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
import neurocombat_modified_fun # Put this function in same path or import from specific location
from neurocombat_modified_fun import neuroCombat_estimate, neuroCombat_transform
from sklearn.preprocessing import StandardScaler

#COMBAT HARMONIZATION  CLASSE: integration of neurocombat function into a python classe

# Limitations:
# Not yet compatible with Random/GridSearchCV from keras
# Cannot choose a CV method different from hold-out
# It can harmonize globals like Total Intracranial Volume (TIV) (which are included in covariates) if feat_of_no_interest is given,
# at the same step in which harmonizes features of interest, BUT only using the fit_transform method: using fit() method and then transform() method harmonized TIV 2xtimes

class ComBatHarmonization(BaseEstimator, TransformerMixin):
  """
  Multi-site neurocombat harmonization compatible with sklearn Pipelines
  
  cv_method : None # Under development
  
  ref_batch : int ID of reference batch/site for M-ComBat OR None for normal ComBat
  
  regression_fit : boolean, set True or False to output data as dictionary {data_harmonized, covariates} or just data_harmonized
  
  feat_detail : a dictionary of dictionaries for describing features details for harmonization - first level the feature name to harmonize,
  second level the corresponding columns or rows id's in data and specific categorical and continuous biological covariates to include in combat
  eg. features_dictionary = {'cortical_thickness': {'id': [columns/row index array], 'categorical': ['Gender'],  'continuous':['Age']},
  'volumes' : {'id': [columns/row index array], 'categorical': ['Gender'],  'continuous':['Age', 'TIV]}}
                          
  feat_of_no_interest : None - advice not to use this attribute, dictionary to include covariates of no interest that need prior harmonization
  before harmonizing features of interest (eg Total intracranial volume should be included as biocovariate in the ComBat model 
  but first should be harmonized because it's a feature derived from the image itself, unlike age or sex.

  Example:
  
  combat_model = ComBatHarmonization(cv_method=None, ref_batch=6, regression_fit=False, feat_detail = features_dictionary , feat_of_no_interest=None)
  
  training_harmonized = combat_model.fit( training_dict )
  test_harmonized = combat_model.transform( test_dict)

  """
  def __init__(self, cv_method, ref_batch, regression_fit, feat_detail, feat_of_no_interest):
    """ Creates a new ComBat """

    # Attribute that defines the CV method
    # Dictionary: cv_strategy or holdout_strategy
    self.cv_method=cv_method # for the moment only None can be given 
    self.ref_batch=ref_batch # reference batch/site if there is one, OR None
    self.regression_fit=regression_fit # output data as dictionary {data, covariates}
    self.feat_detail=feat_detail # information about features of interest (brain features: CT, volumes etc) to be harmonized
    self.feat_of_no_interest=feat_of_no_interest # information about features of NO interest to be harmonized (globals: TIV, total surface area,etc)


  def extract_data(self,X):
    """
    Function is called to extract data since X.
    X dictonary contains the data (samples x features) and
    covariates (samples x covariates) .

    """
    global X_data, covars_fit_sorted

    if type(X) is dict: # data should be given as {'data': array_of_data ; 'covariates': dataframe_of_covariates}
      X_data=X['data'].copy()
      covars_fit_sorted=X['covariates']

    elif self.cv_method: # For now only supports None -> next implementation to work with sklearn GridSearchCV and other CV objects
      X_data=X.copy()
      index=list(X_data.index.values)
      X_data=X_data.to_numpy()
      covars_fit_sorted=self.cv_method['covariates'].iloc[index,:]

    return X_data, covars_fit_sorted

  def check_feat_no_int_harmonization(self,X, covariates, batch=None): # the function to first harmonize features-of-no-interest which are covariates 

    if self.feat_of_no_interest: # Were given as input? Is there covariates to harmonize before harmonizing brain features of interest?
      if hasattr(self, 'n_features_'): # If was already fitted
        print('Applying estimations') # this step is applying combat parameters already estimated
        cov_id=self.feat_of_no_interest['covariate']['id']
        cov_to_harm=covars_fit_sorted[[cov_id]].to_numpy()
        feat_concat=self.feat_of_no_interest['feat_concat']
        X_new=np.concatenate((X[:,feat_concat].copy(),cov_to_harm),axis=1)
        categorical_cols=self.feat_of_no_interest['covariate']['categorical']
        continuous_cols=self.feat_of_no_interest['covariate']['continuous']
        batch_col=['batch']
        X_feat_harm=neuroCombat_transform(dat=np.transpose(X_new), covars=covariates, batch_col=batch_col,
                                          cat_cols=categorical_cols, num_cols=continuous_cols,
                                          estimates=self.combat_estimations_[cov_id])["data"]
        cov_harm=np.transpose(X_feat_harm)[:,-cov_to_harm.shape[1]:]
        covariates.loc[:,(cov_id)]=cov_harm # Covariates are changed 'inplace'

      else: # Not fitted
        print('Fitting the regressor')
        self.combat_estimations_={} # initilize new attribute
        cov_id=self.feat_of_no_interest['covariate']['id'] # extract id of covariate to harmonize
        cov_to_harm=covars_fit_sorted[[cov_id]].to_numpy().copy()
        feat_concat=self.feat_of_no_interest['feat_concat'] # extract id features to harmonize
        X_new=np.concatenate((X[:,feat_concat].copy(),cov_to_harm),axis=1) # concat
        categorical_cols=self.feat_of_no_interest['covariate']['categorical']
        continuous_cols=self.feat_of_no_interest['covariate']['continuous']
        batch_col=['batch']
        if self.ref_batch is not None: # if a reference batch was given apply M-ComBat
          cov_feat_combat=neuroCombat_estimate(dat=np.transpose(X_new),covars=covariates,
                                               batch_col=batch_col, categorical_cols=categorical_cols,
                                               continuous_cols=continuous_cols, ref_batch=self.ref_batch)
          self.combat_estimations_[cov_id]=cov_feat_combat["estimates"]

        else: # else apply original ComBat
          cov_feat_combat=neuroCombat_estimate(dat=np.transpose(X_new),covars=covariates,
                                               batch_col=batch_col, categorical_cols=categorical_cols,
                                               continuous_cols=continuous_cols)
          self.combat_estimations_[cov_id]=cov_feat_combat["estimates"]

        #X_feat_harm=cov_feat_combat["data"]
        #cov_harm=np.transpose(X_feat_harm)[:,-cov_to_harm.shape[1]:]

    return X

  def check_feat_harmonization(self,X,covariates, batch=None):
    output=[]
    if self.feat_detail:
      if hasattr(self, 'n_features_'): # if it was fitted
        ('it was fitted, it enter in transform')
        X_harm=[]
        for key_1,val_1 in self.feat_detail.items():
          id=self.feat_detail[key_1]['id']
          X_feat=X[:,id].copy()
          categorical_cols=self.feat_detail[key_1]['categorical']
          continuous_cols=self.feat_detail[key_1]['continuous']
          batch_col=['batch']
          #dat,covars, batch_col, cat_cols, num_cols,estimates
          X_feat_harm=neuroCombat_transform(dat=np.transpose(X_feat), covars=covariates, batch_col=batch_col,
                                            cat_cols=categorical_cols,num_cols=continuous_cols,
                                            estimates=self.combat_estimations_[key_1])["data"]
          X_harm.append(np.transpose(X_feat_harm)) #list with (samples x feat_i) with final len = feat_of_int
        output=np.concatenate(X_harm, axis=1)  # harm data (samples x feat_all)

      else: #if was not fitted
        batch_col=['batch']
        self.combat_estimations_={}
        for key_1,val_1 in self.feat_detail.items():
          id=self.feat_detail[key_1]['id']
          X_feat=X[:,id].copy()
          categorical_cols=self.feat_detail[key_1]['categorical']
          continuous_cols=self.feat_detail[key_1]['continuous']
          if self.ref_batch is not None:
            combat=neuroCombat_estimate(dat=np.transpose(X_feat),covars=covariates,
                                        batch_col=batch_col,
                                        categorical_cols=categorical_cols,
                                        continuous_cols=continuous_cols, ref_batch=self.ref_batch)
            self.combat_estimations_[key_1]=combat["estimates"]


          else:
            combat=neuroCombat_estimate(dat=np.transpose(X_feat),covars=covariates,
                                        batch_col=batch_col,
                                        categorical_cols=categorical_cols,
                                        continuous_cols=continuous_cols)
            self.combat_estimations_[key_1]=combat["estimates"]

    return output # If it was already fitted, returns harm data, otherwise empty


  def fit(self, X, y=None):

    X, covars_fit_sorted=self.extract_data(X)
    X = check_array(X, accept_sparse=True)

    if self.feat_of_no_interest: # To harmonize TIV or other globals in covariates
      ouput=self.check_feat_no_int_harmonization(X, covars_fit_sorted)

    if self.feat_detail:
      output=self.check_feat_harmonization(X,covars_fit_sorted)

    self.n_features_ = X.shape[1] # For the check_is_fitted method

    return self

  def transform(self, X):

    # Check is fit had been called
    check_is_fitted(self)

    X, covars_fit_sorted=self.extract_data(X)
    #batch_trans_sorted=covars_fit_sorted[['batch']] # We only need the batch

    X = check_array(X, accept_sparse=True)

    if self.feat_of_no_interest:
      output=self.check_feat_no_int_harmonization(X, covars_fit_sorted)
      #The output should be X -> the input data because the covariates are changed inplace

    if self.feat_detail:
      output=self.check_feat_harmonization(X, covars_fit_sorted)
      # The ouput should be the X_harm

    if self.regression_fit==1:
      output={'data': output, 'covariates': covars_fit_sorted}

    return output